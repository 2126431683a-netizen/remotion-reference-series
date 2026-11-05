"""Portable Bailian voice design/TTS helper. Credentials stay in runtime memory.

Requires requests. Importing this module never reads credentials or calls an API.
Personal defaults live outside this skill in CODEX_HOME/voice-profiles/.
"""
import argparse
import base64
import csv
import io
import json
import os
from pathlib import Path
import sys
import wave
from urllib.parse import urlsplit

import requests


TEMPLATE = Path(__file__).resolve().parents[1] / 'assets/qingshu-voice.template.json'


def save_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def local_defaults(config_path=None):
    root = Path(os.getenv('CODEX_HOME') or (Path.home() / '.codex'))
    path = Path(config_path).expanduser() if config_path else root / 'voice-profiles/bailian-local.json'
    if not path.exists():
        if config_path:
            raise ValueError('Local configuration file does not exist')
        return {}
    config = read_json(path)
    for name in ('profile', 'credentialFile'):
        if config.get(name):
            value = Path(config[name]).expanduser()
            config[name] = str(value if value.is_absolute() else path.parent / value)
    return config


def load_credentials(csv_path=None):
    csv_path = csv_path or os.getenv('BAILIAN_CREDENTIALS_CSV')
    if csv_path:
        raw = Path(csv_path).expanduser().read_bytes()
        encodings = ('utf-16',) if raw.startswith((b'\xff\xfe', b'\xfe\xff')) else ('utf-8-sig', 'gb18030')
        for encoding in encodings:
            try:
                text = raw.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            raise ValueError('Cannot decode credential CSV')
        values = {row[0].strip(): row[1].strip() for row in csv.reader(io.StringIO(text)) if len(row) >= 2}
        key, base = values.get('apiKey', ''), values.get('dashScope', '')
    else:
        key, base = os.getenv('DASHSCOPE_API_KEY', ''), os.getenv('BAILIAN_BASE_URL', '')
    if not key or not base:
        raise ValueError('Configure a credential CSV, or DASHSCOPE_API_KEY and BAILIAN_BASE_URL')
    endpoint = urlsplit(base)
    official = endpoint.hostname and (
        endpoint.hostname.endswith('.maas.aliyuncs.com')
        or endpoint.hostname in ('dashscope.aliyuncs.com', 'dashscope-intl.aliyuncs.com')
    )
    if (endpoint.scheme != 'https' or not official or endpoint.query or endpoint.fragment
            or endpoint.username is not None or endpoint.password is not None):
        raise ValueError('Expected an official HTTPS Model Studio endpoint without embedded credentials')
    if endpoint.path.rstrip('/') != '/api/v1':
        raise ValueError('Base URL must end in /api/v1')
    return key, base.rstrip('/')


def finalize_wav(data):
    """Normalize a streaming WAV header, preserving all decoded PCM samples."""
    if data[:4] != b'RIFF':
        raise ValueError('Expected WAV data')
    with wave.open(io.BytesIO(data), 'rb') as source:
        params = source.getparams()
        samples = source.readframes(source.getnframes())
    if not samples or len(samples) % (params.nchannels * params.sampwidth):
        raise ValueError('Empty or incomplete PCM audio')
    destination = io.BytesIO()
    with wave.open(destination, 'wb') as output:
        output.setnchannels(params.nchannels)
        output.setsampwidth(params.sampwidth)
        output.setframerate(params.framerate)
        output.writeframes(samples)
    return destination.getvalue()


def synthesis_parameters(text, profile):
    if profile.get('format', 'wav') != 'wav':
        raise ValueError('This helper saves WAV; set profile format to wav')
    args = {
        'text': text, 'voice': profile['voiceId'], 'format': 'wav',
        'sample_rate': profile.get('sampleRate', 24000),
        'rate': profile.get('rate', 1.2), 'pitch': profile.get('pitch', 1.0),
        'volume': profile.get('volume', 50),
        'language_hints': profile.get('languageHints', [profile.get('language', 'zh')]),
        'instruction': profile.get('instruction', ''),
    }
    if 'seed' in profile:
        args['seed'] = profile['seed']
    return args


def cache_matches(meta, text, profile):
    """Only reuse audio with an exact recorded synthesis configuration."""
    return (meta.get('model') == profile['model']
            and meta.get('synthesisParameters') == synthesis_parameters(text, profile))


class BailianVoice:
    def __init__(self, credential_file=None):
        self.key, self.base = load_credentials(credential_file)
        self.session = requests.Session()

    def clean(self, value):
        return str(value).replace(self.key, '[REDACTED]')

    def post(self, path, payload, stream=False):
        headers = {'Authorization': 'Bearer ' + self.key, 'Content-Type': 'application/json'}
        if stream:
            headers['X-DashScope-SSE'] = 'enable'
        response = self.session.post(self.base + path, headers=headers, json=payload,
                                     timeout=(15, 180), stream=stream, allow_redirects=False)
        if response.status_code != 200:
            try:
                error = response.json()
            except ValueError:
                error = {'message': response.text[:400]}
            if not isinstance(error, dict):
                error = {'message': 'Unexpected error response format'}
            detail = {'httpStatus': response.status_code, 'code': error.get('code'),
                      'message': error.get('message'), 'requestId': error.get('request_id')}
            response.close()
            raise RuntimeError(self.clean(json.dumps(detail, ensure_ascii=False)))
        return response

    def create(self, profile_path, spec):
        profile_path = Path(profile_path)
        if profile_path.exists():
            raise ValueError('Profile already exists; reuse it instead of creating another voice')
        model = spec['model']
        payload = {
            'model': 'voice-enrollment',
            'input': {'action': 'create_voice', 'target_model': model,
                      'voice_prompt': spec['voicePrompt'], 'preview_text': spec['previewText'],
                      'prefix': spec.get('prefix', 'qingshu'),
                      'language_hints': [spec.get('language', 'zh')]},
            'parameters': {'sample_rate': spec.get('sampleRate', 24000), 'response_format': 'wav'},
        }
        with self.post('/services/audio/tts/customization', payload) as response:
            data = response.json()
        output = data.get('output', {})
        if not output.get('voice_id'):
            detail = {key: data.get(key) for key in ('code', 'message', 'request_id')}
            raise RuntimeError(self.clean(json.dumps(detail, ensure_ascii=False)))
        allowed = ('voicePrompt', 'previewText', 'instruction', 'rate', 'pitch', 'volume',
                   'sampleRate', 'format', 'language', 'languageHints', 'seed')
        profile = {key: spec[key] for key in allowed if key in spec}
        profile.update({
            'provider': 'Aliyun Model Studio', 'model': output.get('target_model', model),
            'voiceId': output['voice_id'], 'creationRequestId': data.get('request_id'),
            'creationUsage': data.get('usage'),
            'creationMethod': 'description-based voice design, not training from a real-person recording',
        })
        # Save the reusable ID before handling optional preview data.
        save_json(profile_path, profile)
        preview = output.get('preview_audio', {})
        if preview.get('data'):
            preview_path = profile_path.with_name(profile_path.stem + '-design-preview.wav')
            preview_path.write_bytes(finalize_wav(base64.b64decode(preview['data'], validate=True)))
        return profile

    def query(self, voice_id):
        payload = {'model': 'voice-enrollment', 'input': {'action': 'query_voice', 'voice_id': voice_id}}
        with self.post('/services/audio/tts/customization', payload) as response:
            data = response.json()
        return {key: data.get('output', {}).get(key) for key in ('voice_id', 'target_model', 'status')}

    def synthesize(self, text, profile, out_path, stream=True):
        out_path = Path(out_path)
        if out_path.exists() or out_path.with_suffix('.json').exists():
            raise ValueError('Output exists; validate its cache or choose a new versioned path')
        if out_path.suffix.lower() != '.wav' or not text.strip():
            raise ValueError('Provide nonempty narration and a .wav output path')
        recorded = synthesis_parameters(text, profile)
        args = dict(recorded)
        if stream:
            args['word_timestamp_enabled'] = True
        payload = {'model': profile['model'], 'input': args}
        events, chunks, url = [], [], None
        with self.post('/services/audio/tts/SpeechSynthesizer', payload, stream=stream) as response:
            if stream:
                for line in response.iter_lines():
                    if not line or not line.startswith(b'data:'):
                        continue
                    raw = line[5:].strip()
                    if raw == b'[DONE]':
                        continue
                    data = json.loads(raw)
                    if data.get('code') and data['code'] != 'Success':
                        detail = {key: data.get(key) for key in ('code', 'message', 'request_id')}
                        raise RuntimeError(self.clean(json.dumps(detail, ensure_ascii=False)))
                    output = data.get('output', {})
                    audio = output.get('audio', {})
                    if audio.get('data'):
                        chunks.append(base64.b64decode(audio['data'], validate=True))
                    if audio.get('url'):
                        url = audio['url']
                    events.append({'type': output.get('type'), 'finishReason': output.get('finish_reason'),
                                   'originalText': output.get('original_text'), 'sentence': output.get('sentence'),
                                   'usage': data.get('usage'), 'requestId': data.get('request_id')})
            else:
                data = response.json()
                output = data.get('output', {})
                url = output.get('audio', {}).get('url')
                events.append({'finishReason': output.get('finish_reason'),
                               'usage': data.get('usage'), 'requestId': data.get('request_id')})
        if not any(event.get('finishReason') == 'stop' for event in events):
            raise RuntimeError('TTS ended without a completion marker; no audio saved')
        started = {(event.get('sentence') or {}).get('index') for event in events
                   if event.get('type') == 'sentence-begin'}
        ended = {(event.get('sentence') or {}).get('index') for event in events
                 if event.get('type') == 'sentence-end'}
        if started - ended:
            raise RuntimeError('TTS has unfinished sentences; no audio saved')
        if chunks:
            audio_data = b''.join(chunks)
        elif url:
            endpoint = urlsplit(url)
            if (endpoint.scheme != 'https' or endpoint.username is not None or endpoint.password is not None
                    or not endpoint.hostname or not endpoint.hostname.endswith('.aliyuncs.com')):
                raise RuntimeError('Unexpected audio download endpoint')
            # Signed result URLs need no API Authorization header.
            try:
                with requests.get(url, timeout=(15, 90), allow_redirects=False) as download:
                    if download.status_code != 200:
                        raise RuntimeError('Audio download failed with HTTP ' + str(download.status_code))
                    audio_data = download.content
            except requests.RequestException as error:
                # Transport exceptions may include the signed URL; report only their type.
                raise RuntimeError('Audio download failed: ' + type(error).__name__) from None
        else:
            raise RuntimeError('No generated audio returned')
        audio_data = finalize_wav(audio_data)
        meta = {'model': profile['model'], 'voiceId': profile['voiceId'],
                'rate': args['rate'], 'pitch': args['pitch'], 'volume': args['volume'],
                'instruction': args['instruction'], 'sampleRate': args['sample_rate'],
                'format': args['format'], 'text': text, 'bytes': len(audio_data),
                'synthesisParameters': recorded, 'events': events}
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(audio_data)
        save_json(out_path.with_suffix('.json'), meta)
        return meta


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['create', 'query', 'synthesize'])
    parser.add_argument('--local-config', help='Non-secret local JSON; defaults outside the skill under CODEX_HOME')
    parser.add_argument('--credential-file', help='Credential CSV read only at runtime; never printed')
    parser.add_argument('--profile', help='Reusable voice profile; or BAILIAN_VOICE_PROFILE/local config for reuse')
    parser.add_argument('--voice-config', default=str(TEMPLATE), help='Voice description/settings template for create')
    parser.add_argument('--text-file')
    parser.add_argument('--output')
    parser.add_argument('--non-streaming', action='store_true')
    args = parser.parse_args()
    client = None
    try:
        config = local_defaults(args.local_config)
        if args.action == 'create' and not args.profile:
            raise ValueError('Creating a voice requires an explicit new --profile path')
        profile_path = args.profile or os.getenv('BAILIAN_VOICE_PROFILE') or config.get('profile')
        if not profile_path:
            raise ValueError('Set --profile, BAILIAN_VOICE_PROFILE, or a local default profile')
        credential_file = args.credential_file or os.getenv('BAILIAN_CREDENTIALS_CSV')
        # Explicit environment credentials override a saved local CSV default.
        if not credential_file and not (os.getenv('DASHSCOPE_API_KEY') and os.getenv('BAILIAN_BASE_URL')):
            credential_file = config.get('credentialFile')
        client = BailianVoice(credential_file)
        if args.action == 'create':
            profile = client.create(profile_path, read_json(args.voice_config))
            print(json.dumps({'created': True, 'model': profile['model'], 'profile': str(profile_path)}, ensure_ascii=False))
        elif args.action == 'query':
            print(json.dumps(client.query(read_json(profile_path)['voiceId']), ensure_ascii=False))
        else:
            if not args.text_file or not args.output:
                raise ValueError('--text-file and --output are required')
            profile = read_json(profile_path)
            text = Path(args.text_file).read_text(encoding='utf-8-sig').strip()
            meta = client.synthesize(text, profile, args.output, not args.non_streaming)
            print(json.dumps({'saved': args.output, 'bytes': meta['bytes'], 'rate': meta['rate'],
                              'events': len(meta['events'])}, ensure_ascii=False))
    except Exception as error:
        message = client.clean(error) if client else str(error)
        print(message, file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
