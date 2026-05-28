import copy
import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.error
import urllib.request

os.environ["TOKENIZERS_PARALLELISM"] = "false"

API_DIR = Path(__file__).resolve().parent
SRC_DIR = API_DIR.parent / 'src'
sys.path.insert(0, str(SRC_DIR))
import constants
import parser
import process
from summ_dataset import (
    add_key_val_pair,
    n_tokens,
    remove_sample,
    SummDataset,
)

LEN_TIMEOUT = 30 # seconds for api timeout
    

def main():
    ''' calls the Gemini Developer API '''

    args, dataset = load_data_()

    # files across all samples
    fn_log = os.path.join(args.dir_out, 'log.txt')
    fn_result = os.path.join(args.dir_out, 'result.jsonl')
    fn_naughty = os.path.join(args.dir_out, 'naughty.csv')
    naughty_lst = get_naughty_list(fn_naughty)

    # directories for individual samples
    dir_indiv = os.path.join(args.dir_out, 'indiv')
    dir_inp = os.path.join(dir_indiv, 'inp')
    dir_inp_proc = os.path.join(dir_indiv, 'inp_proc')
    dir_out_ = os.path.join(dir_indiv, 'out')
    dir_result = os.path.join(dir_indiv, 'results')
    for dir_ in [dir_inp, dir_inp_proc, dir_out_, dir_result]:
        if not os.path.exists(dir_):
            os.makedirs(dir_)

    # filter out pre-generated samples, add system prompt
    idcs_pregen = get_completed_idcs(dir_result)
    for sample in copy.deepcopy(dataset.data):
        if sample['idx'] in idcs_pregen:
            remove_sample(dataset.data, sample['idx'])
        else:    
            add_key_val_pair(dataset.data, idx=sample['idx'],
                             key='system_prompt', value=args.instruction)
    if len(idcs_pregen):
        msg = f'filtered out {len(idcs_pregen)} pre-generated samples. '
        msg += f'querying Gemini for {len(dataset.data)} remaining samples'
        print(msg)

    for sample in dataset.data:
       
        t0 = time.time()
        idx = sample['idx']
        tgt = sample['target']
        fn_ = f'{idx}.jsonl'

        if idx in naughty_lst: # sample indices previously rejected by API
            continue

        # get individual filenames
        fn_inp_ = get_path(dir_inp, fn_, rm=True)
        fn_inp_proc_ = get_path(dir_inp_proc, fn_, rm=True)
        fn_out = get_path(dir_out_, fn_, rm=True)
        fn_result_ = os.path.join(dir_result, fn_)

        sample = [sample] # convert to list so we can use built-ins
        process.write_list_to_jsonl(fn_inp_, sample)

        # Pre-process the prompt into a Gemini generateContent request.
        cmd = [
            sys.executable, 'preprocess.py', fn_inp_, fn_inp_proc_,
            '--system_prompt', args.instruction,
            '--temperature', str(args.gpt_temp),
        ]
        subprocess.run(cmd, cwd=API_DIR, check=True)

        # Query Gemini.
        try:
            t0 = time.time()
            out = call_api_wrapper(args, fn_inp_proc_, fn_out)
            t1 = round(time.time() - t0, 1)
            now = str(datetime.datetime.now()).split('.')[0]
            if not out: # if Gemini gave an error
                msg = f'sample {idx} exited w error in {t1} seconds, {now}'
                log_progress(fn_log, msg)
                continue
            msg = f'sample {idx} processed in {t1} seconds, {now}'
            log_progress(fn_log, msg)

        except TimeoutError:
            now = str(datetime.datetime.now()).split('.')[0]
            msg = f'sample {idx} timed out given {LEN_TIMEOUT} seconds, {now}'
            log_progress(fn_log, msg)
            with open(fn_naughty, 'a') as f:
                f.write(f'{idx}\n')
            continue
       
        # postprocess output
        out = process.postprocess(args, out)
        add_key_val_pair(lst=sample, idx=idx, key='output', value=out)
        r_tok = round(n_tokens(out) / n_tokens(tgt), 3)
        add_key_val_pair(sample, idx=idx, key='ratio_tok', value=r_tok)

        # save indiv file
        process.write_list_to_jsonl(fn_result_, sample)

    # load all indiv files, save to one for expmt
    fn_out_lst = get_files(dir_result)
    results_all = []
    for fn_out in fn_out_lst:
        results_all.append(process.read_jsonl_to_list(fn_out)[0])
    process.write_list_to_jsonl(fn_result, results_all)
    print(f'results generated in {args.dir_out}\n\n\n\n\n')


def load_data_():
    ''' load data for api call
        determine which samples, add system prompt '''

    args = parser.get_parser(purpose='api')

    args = get_gemini_configs(args)
  
    # load inputs
    dataset = SummDataset(args, task='test', create_dataset_obj=False)
    dataset.save_data(args, fn_out='inputs.jsonl')

    return args, dataset


def call_api_wrapper(args, fn_inp_proc_, fn_out):
    ''' Call Gemini for one prepared request and return generated text. '''

    request_body = process.read_jsonl_to_list(fn_inp_proc_)[0]
    metadata = request_body.pop('metadata')
    request = urllib.request.Request(
        constants.GEMINI_URL_MODEL[args.model],
        data=json.dumps(request_body).encode('utf-8'),
        headers={
            'Content-Type': 'application/json',
            'x-goog-api-key': args.gemini_api_key,
        },
        method='POST',
    )
    try:
        with urllib.request.urlopen(request, timeout=LEN_TIMEOUT) as response:
            api_response = json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as exc:
        raw_response = exc.read().decode('utf-8')
        try:
            api_response = json.loads(raw_response)
        except json.JSONDecodeError:
            api_response = {'error': {'code': exc.code, 'message': raw_response}}

    process.write_list_to_jsonl(
        fn_out, [[request_body, api_response, metadata]]
    )
    if 'error' in api_response:
        log_api_exit(args, metadata, api_response)
        return None

    try:
        parts = api_response['candidates'][0]['content']['parts']
    except (KeyError, IndexError):
        log_api_exit(args, metadata, api_response)
        return None
    return ''.join(part.get('text', '') for part in parts).strip()


def get_gemini_configs(args):
    ''' Load the Gemini API key from the environment or repository .env. '''

    if not constants.GEMINI_API_KEY:
        raise NotImplementedError('set GEMINI_API_KEY in .env or your environment')
    args.gemini_api_key = constants.GEMINI_API_KEY
    return args


def log_api_exit(args, metadata, api_response):
    fn_exit = get_path(args.dir_out, 'exit_log.csv', rm=False)
    process.write_list_to_csv(
        fn_exit, [metadata['idx'], json.dumps(api_response)]
    )


def get_naughty_list(fn_naughty):
    ''' list of sample indices previously rejected by the API
        track s.t. we avoid them in future runs '''
    
    if not os.path.exists(fn_naughty):
        return []

    with open(fn_naughty, 'r') as f:
        lines = f.readlines()
    naughty_lst = [line.strip() for line in lines if line.strip()]

    return naughty_lst


def get_path(dir_, fn, rm=False):

    path = os.path.join(dir_, fn)
   
    # delete old version of that file
    if rm:
        try:
            os.remove(path)
        except OSError:
            pass

    return path


def log_progress(fn_log, msg):
    with open(fn_log, 'a') as f:
        f.write(msg + '\n')


def get_files(dir_, abs_path=True):
    ''' get all files in a directory '''
    f_lst = [f for f in os.listdir(dir_) if os.path.isfile(os.path.join(dir_, f))]
    if abs_path:
        f_lst = [os.path.join(dir_, f) for f in f_lst]
    return f_lst


def get_completed_idcs(dir_):
    ''' get indices of files in a directory, i.e. xxx from xxx.jsonl '''
    f_lst = get_files(dir_, abs_path=False)
    idx_lst = [int(f.split('.')[0]) for f in f_lst] 
    return idx_lst


if __name__ == '__main__':
    main()
