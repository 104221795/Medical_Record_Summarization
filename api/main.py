from pathlib import Path
import subprocess
import sys


API_DIR = Path(__file__).resolve().parent


def main():
    ''' wrapper to call the Gemini runner using a dictionary
        of dataset : case_id_list pairs '''

    # TODO: manually set these params for each set of expmts
    task = 'run' # 'run' (query Gemini), 'calc' (metrics)
    expmt_name_list = ['demo'] # per expmts defined in get_expmt_configs()
    is_demo = True # enable runs over 1 sample (else constants.N_MIN_SAMPLES)

    for expmt_name in expmt_name_list:

        case_ids, model, n_samples = get_expmt_configs(expmt_name)
        dataset_list = ['opi', 'chq']
        assert task in ['run', 'calc']
        script = 'run_expmt.py'
        
        if task == 'run':
            cmd = [sys.executable, script, '--n_samples', str(n_samples),
                   '--model', model]
            if is_demo:
                cmd.append('--is_demo')
        elif task == 'calc':
            cmd = [sys.executable, '../src/calc_metrics.py', '--n_samples',
                   '9999', '--model', model]

        for dataset in dataset_list:
            
            case_id_list = case_ids[dataset]
            
            for case_id in case_id_list:
                cmd_case = cmd + ['--dataset', dataset,
                                  '--case_id', str(case_id)]
                subprocess.run(cmd_case, cwd=API_DIR, check=True)
            

def get_expmt_configs(expmt_name):
    ''' TODO: define experimental configurations, i.e.
            model (for example, gemini-2.5-flash-lite)
            case_ids: corresponding to configs in constants.cases
            datasets, e.g. opi or chq '''

    assert expmt_name in ['demo']
    
    if expmt_name == 'demo':
        n_samples = 1 # number of samples to run
        model = 'gemini-2.5-flash-lite'
        case_ids = {'opi': [400], 'chq': []} # case_id=400 for opi dataset

    else:
        raise NotImplementedError


    return case_ids, model, n_samples


if __name__ == '__main__':
    main()
