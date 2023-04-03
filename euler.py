import json
import os
import sys
from PIL import Image
import wandb
import numpy as np
import time
from distutils import spawn

from utils import run, calculate_metrics_perpixAP, list_img_from_dir


def main():
    pr_id = json.loads(sys.argv[1])
    print(f'pr_id: {pr_id}', flush=True)
    dataset = sys.argv[2]
    print(f'{dataset=}', flush=True)
    assert dataset in ['lostandfound_fishyscapes', 'fishyscapes_static_ood', 'fishyscapes_5000timingsamples']
    

    with open('settings.json', 'r') as f:
        settings = json.load(f)

    # make directories and copy data
    img_path = os.path.join(os.environ['TMPDIR'], 'inputs')
    run(['mkdir', img_path])
    run(['cp', f'/cluster/work/riner/users/fishyscapes/{dataset}/test_images.zip', os.environ['TMPDIR']])
    run(['unzip', os.path.join(os.environ['TMPDIR'], 'test_images.zip'), '-d', img_path])
    out_path = os.path.join(os.environ['TMPDIR'], 'outputs')
    run(['mkdir', out_path])
    simg_path = os.path.join(os.environ['TMPDIR'], 'image.simg')
    run(['cp', os.path.join('/cluster', 'scratch', 'blumh', f'fishyscapes_pr_{pr_id}'), simg_path])

    cmd = [
        'singularity', 'run', '--nv', '--writable-tmpfs', '-W', os.environ['TMPDIR'],
        '--bind', f"{out_path}:/output,"
                  f"{img_path}:/input",
        simg_path
    ]
    try:
        start = time.time()
        run(cmd)
        end = time.time()
    except AssertionError:
        raise UserWarning("Execution of submitted container failed. Please take a look at the logs and resubmit a new container.")

    # get evaluation labels
    label_path = os.path.join(os.environ['TMPDIR'], 'labels')
    run(['mkdir', label_path])
    run(['cp', f'/cluster/work/riner/users/fishyscapes/{dataset}/test_labels.zip', os.environ['TMPDIR']])
    run(['unzip', os.path.join(os.environ['TMPDIR'], 'test_labels.zip'), '-d', label_path])

    # evaluate outputs
    labels = list_img_from_dir(label_path, '_labels.png')[:1000]
    labels = [np.asarray(Image.open(p)) for p in labels]
    scores = list_img_from_dir(out_path, '_anomaly.npy')[:1000]
    scores = [np.load(p) for p in scores]

    ret = calculate_metrics_perpixAP(labels, scores)
    ret['inference_time'] = end - start
    print(ret, flush=True)
    wandb.init(project='fishyscapes', 
               name=f"{pr_id}-{dataset}",
               #mode='offline',
               config=dict(pr=pr_id, dataset=dataset))
    wandb.log(ret)
    #wandb.finish()


if __name__ == '__main__':
    main()
