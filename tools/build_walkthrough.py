"""Render a 180-second walkthrough from actual app captures and local narration.

Requires optional requirements-video.txt and nine WAV narrations. No upload.
"""
import argparse
import json
from pathlib import Path
import subprocess
import textwrap
import wave
import imageio_ffmpeg

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--folder',type=Path,default=ROOT/'outputs/step10')
    parser.add_argument('--captions-only',action='store_true',help='Render a silent, captioned walkthrough without WAV files')
    args=parser.parse_args();folder=args.folder.resolve();frames=folder/'video-frames';render=folder/'video-render';render.mkdir(exist_ok=True)
    scenes=json.loads((ROOT/'docs/walkthrough.json').read_text(encoding='utf-8'))
    ffmpeg=imageio_ffmpeg.get_ffmpeg_exe()
    font=Path('C:/Windows/Fonts/arial.ttf')
    if not font.exists():font=Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
    font_arg=font.as_posix().replace(':',r'\:')
    subtitles=[]
    for i,scene in enumerate(scenes,1):
        audio=folder/f'narration-{i:02d}.wav'
        duration=0
        if not args.captions_only:
            with wave.open(str(audio),'rb') as w:duration=w.getnframes()/w.getframerate()
        speed=max(1,duration/19)
        (render/f'title-{i}.txt').write_text('\n'.join(textwrap.wrap(scene['title'],30)),encoding='utf-8',newline='\n')
        (render/f'body-{i}.txt').write_text('\n'.join(textwrap.wrap(scene['text'],40)),encoding='utf-8',newline='\n')
        footer='Actual app captures | '+('Captioned walkthrough' if args.captions_only else 'Synthetic narration')+'\nSolver waits shortened | Planning drafts only'
        (render/'footer.txt').write_text(footer,encoding='utf-8',newline='\n')
        filters=(f"[0:v]scale=650:650:force_original_aspect_ratio=decrease,pad=1280:720:25:(oh-ih)/2:color=0x112833,setsar=1,"
                 f"drawtext=fontfile='{font_arg}':textfile='title-{i}.txt':fontcolor=0x70d8c2:fontsize=31:line_spacing=10:x=710:y=70,"
                 f"drawtext=fontfile='{font_arg}':textfile='body-{i}.txt':fontcolor=white:fontsize=23:line_spacing=11:x=710:y=190,"
                 f"drawtext=fontfile='{font_arg}':textfile='footer.txt':fontcolor=0xa8bfc5:fontsize=16:line_spacing=8:x=710:y=650[v];"
                 f"[1:a]atempo={speed:.6f},apad[a]")
        audio_input=['-f','lavfi','-i','anullsrc=channel_layout=stereo:sample_rate=48000'] if args.captions_only else ['-i',str(audio)]
        cmd=[ffmpeg,'-y','-hide_banner','-loglevel','error','-loop','1','-i',str(frames/scene['image']),*audio_input,
             '-filter_complex',filters,'-map','[v]','-map','[a]','-t','20','-r','24','-c:v','libx264','-preset','veryfast','-crf','22',
             '-pix_fmt','yuv420p','-c:a','aac','-ar','48000',str(render/f'scene-{i:02d}.mp4')]
        subprocess.run(cmd,cwd=render,check=True)
        start=(i-1)*20;end=i*20
        stamp=lambda seconds:f'00:{seconds//60:02d}:{seconds%60:02d},000'
        subtitles.append(f'{i}\n{stamp(start)} --> {stamp(end)}\n{scene["text"]}\n')
    (render/'concat.txt').write_text(''.join(f"file 'scene-{i:02d}.mp4'\n" for i in range(1,10)),encoding='utf-8')
    target=folder/'tracklight-walkthrough.mp4'
    subprocess.run([ffmpeg,'-y','-hide_banner','-loglevel','error','-f','concat','-safe','0','-i','concat.txt','-c','copy','-movflags','+faststart',str(target)],cwd=render,check=True)
    (folder/'tracklight-walkthrough.srt').write_text('\n'.join(subtitles),encoding='utf-8')
    record={'duration_seconds':180,'scenes':9,'resolution':'1280x720','frames_per_second':24,'ffmpeg_version':imageio_ffmpeg.get_ffmpeg_version(),
            'source':'Actual browser screenshots; waits compressed. No external music or footage.',
            'audio':'silent; explanatory on-screen captions' if args.captions_only else 'synthetic local Windows speech narration',
            'youtube_publication':'NOT_PUBLISHED'}
    (folder/'video-manifest.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    print(target)


if __name__=='__main__':main()
