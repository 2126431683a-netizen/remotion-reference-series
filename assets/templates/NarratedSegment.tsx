import React from 'react';
import {Audio} from '@remotion/media';
import {Sequence,staticFile,useCurrentFrame,useVideoConfig} from 'remotion';

export type SegmentCaption={text:string;start:number;end:number};
export type NarratedSegmentProps={
  audio:string;
  captions:SegmentCaption[];
  audioOffsetSeconds?:number;
  playbackRate?:number;
  volume?:number;
  captionStyle?:React.CSSProperties;
  children?:React.ReactNode;
};

// Place inside the segment's Sequence. Captions use original audio seconds;
// the parent provides the local frame and clips the segment. Paths are public-relative.
export const NarratedSegment:React.FC<NarratedSegmentProps>=({
  audio,captions,audioOffsetSeconds=0,playbackRate=1,volume=.95,captionStyle,children,
})=>{
  const {fps}=useVideoConfig();
  const frame=useCurrentFrame();
  if(playbackRate<=0||audioOffsetSeconds<0)throw new Error('Invalid narration timing');
  const offsetFrames=Math.round(audioOffsetSeconds*fps);
  const audioTime=(frame-offsetFrames)/fps*playbackRate;
  const caption=captions.find(c=>audioTime>=c.start&&audioTime<c.end);
  return <>
    {children}
    <Sequence from={offsetFrames} premountFor={fps}>
      <Audio src={staticFile(audio)} playbackRate={playbackRate} volume={volume}/>
    </Sequence>
    {caption&&<div style={{position:'absolute',left:'6%',right:'6%',bottom:'4%',display:'flex',justifyContent:'center',pointerEvents:'none'}}>
      <div style={{padding:'10px 24px',background:'#292637',color:'#FFFCF1',fontSize:34,lineHeight:1.45,textAlign:'center',maxWidth:'100%',...captionStyle}}>{caption.text}</div>
    </div>}
  </>;
};
