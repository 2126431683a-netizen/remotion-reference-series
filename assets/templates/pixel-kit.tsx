import React from 'react';
import {AbsoluteFill, Easing, Img, interpolate, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
// Load the destination project's licensed fonts in its entry point.
// Copy assets/channel/channel-sprites.png to public/pixel/channel-sprites.png.

export const P = {
  cream:'#F5F0DF',ink:'#292535',panel:'#292637',panel2:'#3C374B',muted:'#8D8698',
  orange:'#F77C3E',teal:'#44B7AE',yellow:'#F5CF65',green:'#71C783',red:'#E85D69',
  blue:'#6CA8DB',purple:'#9C85CB',line:'#D5CAB6',white:'#FFFCF1',
} as const;
const font='"Noto Sans SC", sans-serif';
export const useTime=()=>useCurrentFrame()/useVideoConfig().fps;
export const ease=(t:number,from:number,to:number,a=0,b=1)=>interpolate(t,[from,to],[a,b],{easing:Easing.bezier(.22,1,.36,1),extrapolateLeft:'clamp',extrapolateRight:'clamp'});

export const Stage:React.FC<{dark?:boolean;children:React.ReactNode}>=({dark=false,children})=><AbsoluteFill style={{background:dark?P.panel:P.cream,color:dark?P.cream:P.ink,fontFamily:font,overflow:'hidden'}}>
  <AbsoluteFill style={{opacity:dark?.2:.14,backgroundImage:`linear-gradient(${dark?P.muted:P.line} 1px,transparent 1px),linear-gradient(90deg,${dark?P.muted:P.line} 1px,transparent 1px)`,backgroundSize:dark?'42px 42px':'84px 84px'}}/>
  <svg width="1920" height="1080" style={{position:'absolute',inset:0,opacity:dark?.1:.19}}>{Array.from({length:150},(_,i)=><rect key={i} x={(i*193+71)%1920} y={(i*137+33)%1080} width={i%4===0?5:2} height={i%4===0?5:2} fill={[P.orange,P.teal,P.muted][i%3]}/>)}</svg>
  <svg width="1920" height="1080" style={{position:'absolute',inset:0,opacity:.55}}><path d="M58 105 V58 H105 M1815 58 H1862 V105 M58 975 V1022 H105 M1815 1022 H1862 V975" fill="none" stroke={dark?P.muted:P.line} strokeWidth="4"/></svg>
  {children}
</AbsoluteFill>;

export const Label:React.FC<{children:React.ReactNode;x:number;y:number;size?:number;color?:string;style?:React.CSSProperties}>=({children,x,y,size=44,color,style})=><div style={{position:'absolute',left:x,top:y,fontFamily:font,fontSize:size,fontWeight:650,lineHeight:1.4,color,...style}}>{children}</div>;

export const Block:React.FC<{children?:React.ReactNode;x:number;y:number;w?:number;h?:number;color?:string;dark?:boolean;style?:React.CSSProperties}>=({children,x,y,w=160,h=76,color=P.orange,dark=false,style})=><div style={{position:'absolute',left:x,top:y,width:w,height:h,background:color,border:`3px solid ${P.ink}`,boxShadow:`5px 5px 0 ${dark?'#171520':P.line}`,display:'flex',alignItems:'center',justifyContent:'center',fontSize:34,fontWeight:700,color:P.ink,whiteSpace:'nowrap',...style}}>{children}</div>;

export const PixelPanel:React.FC<{x:number;y:number;w:number;h:number;dark?:boolean;color?:string;title?:string;children?:React.ReactNode;style?:React.CSSProperties}>=({x,y,w,h,dark=false,color,title,children,style})=><div style={{position:'absolute',left:x,top:y,width:w,height:h,background:color??(dark?P.panel2:P.white),border:`3px solid ${dark?P.muted:P.ink}`,boxShadow:`7px 7px 0 ${dark?'#181622':P.line}`,color:dark?P.cream:P.ink,...style}}>
  {title&&<div style={{position:'absolute',left:0,top:0,right:0,height:51,borderBottom:`2px solid ${dark?P.muted:P.line}`,padding:'6px 20px',fontSize:25,fontWeight:700}}>{title}</div>}
  {[{left:5,top:5},{right:5,top:5},{left:5,bottom:5},{right:5,bottom:5}].map((pos,i)=><span key={i} style={{position:'absolute',...pos,width:4,height:4,background:dark?P.cream:P.ink,opacity:.55}}/>)}
  {children}
</div>;

export const Sprite:React.FC<{kind:'host'|'robot';pose?:0|1|2;x:number;y:number;size?:number;flip?:boolean}>=({kind,pose=0,x,y,size=260,flip=false})=>{
  const crop={x:pose*512,y:kind==='host'?0:620,w:512,h:kind==='host'?620:404};
  const scale=Math.min(size/crop.w,size/crop.h);
  return <div style={{position:'absolute',left:x,top:y,width:size,height:size,transform:flip?'scaleX(-1)':undefined}}><div style={{position:'absolute',left:(size-crop.w*scale)/2,top:(size-crop.h*scale)/2,width:crop.w*scale,height:crop.h*scale,overflow:'hidden'}}><Img src={staticFile('pixel/channel-sprites.png')} style={{position:'absolute',left:-crop.x*scale,top:-crop.y*scale,width:1536*scale,height:1024*scale,maxWidth:'none',imageRendering:'pixelated'}}/></div></div>;
};

export type PixelIconName='chip'|'document'|'book'|'tool'|'database'|'ticket'|'shield'|'search'|'check'|'cross'|'arrow'|'brain'|'train'|'coin';
export const Icon:React.FC<{name:PixelIconName;x:number;y:number;size?:number;color?:string}>=({name,x,y,size=96,color=P.orange})=>{
  const shapes:Record<PixelIconName,React.ReactNode>={
    chip:<><path d="M7 3V8M13 3V8M19 3V8M25 3V8M7 24V29M13 24V29M19 24V29M25 24V29M3 10H8M3 17H8M3 24H8M24 10H29M24 17H29M24 24H29"/><rect x="7" y="7" width="18" height="18" fill={color}/><rect x="12" y="12" width="8" height="8" fill={P.white}/></>,
    document:<><path d="M7 3H21L26 8V29H7Z" fill={P.white}/><path d="M21 3V9H26M11 14H22M11 19H22M11 24H18"/><rect x="9" y="8" width="7" height="3" fill={color} stroke="none"/></>,
    book:<><path d="M3 5H14L16 8L18 5H29V26H18L16 29L14 26H3Z" fill={color}/><path d="M16 8V29M7 11H12M7 16H12M20 11H25M20 16H25"/></>,
    tool:<><path d="M21 3H29V11L23 16L10 29L3 22L16 9V3L21 8L25 7Z" fill={color}/><rect x="7" y="21" width="3" height="3" fill={P.white}/></>,
    database:<><path d="M5 5H27V27H5Z" fill={color}/><path d="M5 11H27M5 20H27M9 4V1H23V4"/><rect x="9" y="14" width="14" height="3" fill={P.white} stroke="none"/></>,
    ticket:<><path d="M3 7H29V12H26V20H29V25H3V20H6V12H3Z" fill={color}/><path d="M21 8V24M10 13H17M10 18H17"/></>,
    shield:<><path d="M16 2L28 7V18L23 25L16 30L9 25L4 18V7Z" fill={color}/><path d="M10 15L14 20L23 11" stroke={P.white}/></>,
    search:<><path d="M4 4H20V8H24V20H20V24H8V20H4Z" fill={P.white}/><path d="M22 22L29 29" strokeWidth="5"/><rect x="9" y="9" width="8" height="8" fill={color} stroke="none"/></>,
    check:<path d="M4 16L12 24L28 7" fill="none" stroke={color} strokeWidth="5"/>,
    cross:<path d="M7 7L25 25M25 7L7 25" fill="none" stroke={color} strokeWidth="5"/>,
    arrow:<path d="M3 12H19V5L29 16L19 27V20H3Z" fill={color}/>,
    brain:<><path d="M16 5L12 2L7 5V9L3 12V21L7 25H12L16 30L20 25H25L29 21V12L25 9V5L20 2Z" fill={color}/><path d="M16 5V26M8 12H12V17M24 12H20V21M8 22H12"/></>,
    train:<><path d="M6 3H26V24H6Z" fill={color}/><path d="M9 7H23V16H9Z" fill={P.white}/><path d="M10 24L5 30M22 24L27 30M8 28H24"/><rect x="9" y="19" width="4" height="3" fill={P.white}/><rect x="19" y="19" width="4" height="3" fill={P.white}/></>,
    coin:<><path d="M10 2H22V5H27V10H30V22H27V27H22V30H10V27H5V22H2V10H5V5H10Z" fill={color}/><path d="M19 9H12V15H20V22H12M16 6V25"/></>,
  };
  return <svg viewBox="0 0 32 32" width={size} height={size} shapeRendering="crispEdges" style={{position:'absolute',left:x,top:y,overflow:'visible',filter:`drop-shadow(3px 3px 0 ${P.ink}22)`}}><g stroke={P.ink} strokeWidth="2" strokeLinejoin="miter">{shapes[name]}</g></svg>;
};

export const Arrow:React.FC<{x1:number;y1:number;x2:number;y2:number;progress?:number;color?:string;dashed?:boolean}>=({x1,y1,x2,y2,progress=1,color=P.orange,dashed=false})=>{
  const p=Math.max(0,Math.min(1,progress));const x=x1+(x2-x1)*p,y=y1+(y2-y1)*p,angle=Math.atan2(y2-y1,x2-x1)*180/Math.PI;
  return <svg width="1920" height="1080" style={{position:'absolute',inset:0,pointerEvents:'none',overflow:'visible'}}><path d={`M${x1} ${y1}L${x} ${y}`} fill="none" stroke={color} strokeWidth="4" strokeDasharray={dashed?'10 9':undefined}/>{p>.03&&<path d="M-14 -9L0 0L-14 9" transform={`translate(${x} ${y}) rotate(${angle})`} fill="none" stroke={color} strokeWidth="4"/>}</svg>;
};
