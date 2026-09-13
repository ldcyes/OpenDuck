"""Bounded subprocess worker; requires separately installed open-source backends."""
import argparse,json,subprocess,sys
from pathlib import Path


def main():
    p=argparse.ArgumentParser();p.add_argument('kind',choices=['asr','tts']);p.add_argument('input');p.add_argument('output')
    p.add_argument('--model-dir');p.add_argument('--language',default='zh');p.add_argument('--voice',default='cmn');p.add_argument('--threads',type=int,default=2)
    a=p.parse_args()
    if a.kind=='asr':
        if not a.model_dir or any(not (Path(a.model_dir)/name).is_file() for name in ('model.bin','tokenizer.json','config.json')):
            raise ValueError('complete local model and tokenizer required; downloads refused')
        from faster_whisper import WhisperModel
        # Local files only. The HTTP worker never implicitly downloads a model.
        model=WhisperModel(a.model_dir,device='cpu',compute_type='int8',cpu_threads=a.threads,local_files_only=True)
        segments,_=model.transcribe(a.input,language=a.language,beam_size=1,condition_on_previous_text=False,vad_filter=False)
        text=''.join(segment.text for segment in segments).strip()
        if not 1<=len(text)<=4000:raise ValueError('no valid transcript')
        Path(a.output).write_text(json.dumps({'text':text},ensure_ascii=False),encoding='utf8')
    else:
        text=Path(a.input).read_text(encoding='utf8')
        # User text goes only to stdin, never into executable names or options.
        subprocess.run(['espeak-ng','-v',a.voice,'-s','160','-w',a.output,'--stdin'],
                       input=text.encode('utf8'),check=True,timeout=10,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)


if __name__=='__main__':main()
