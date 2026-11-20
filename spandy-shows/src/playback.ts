/** Recording a prefix never moves the learner's playback cursor. */
export function retainedStep(selected:number, length:number, requested:number|null=null){
 return Math.max(0,Math.min(requested??selected,Math.max(0,length-1)));
}
export function playbackOutput(mode:'run'|'visualize', preparing:boolean, atInput:boolean, recorded:string, live:string){
 return (mode==='run'&&preparing)||atInput?live:recorded;
}
