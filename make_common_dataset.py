import glob
import os
import pandas as pd
from scipy import sparse
from scipy.sparse import save_npz
import shutil


# read the data from the given subjects
subjects = 'all'
signal_type = 'grad'
n_parcels_max = 1
no_parcels = 42

# combine them in one datafile with each sample: data from electrodes,
# subject_name, signal_type
data_type = '_' + str(no_parcels) + '_' + str(n_parcels_max)
data_dir_all = 'data/data_' + signal_type + '_all' + data_type
data_dir = ('data/data_' + signal_type + '_*' + data_type)

if os.path.isdir(data_dir_all):
    print('removing contents from ' + data_dir_all)
    shutil.rmtree(data_dir_all)
data_dirs = sorted(glob.glob(data_dir))
os.mkdir(data_dir_all)

# if the all_data directory is still in the list of dirs, remove it
if data_dir_all in data_dirs:
    data_dirs.remove(data_dir_all)
assert data_dir_all not in data_dirs

sbj_id = 0
# initialize the files in the data_dir_all
all_X_file = os.path.join(data_dir_all, 'X.csv')
for idx, subject_path in enumerate(data_dirs):
    # check if all the necessary files are present
    subject_info = subject_path.split('_')
    subject_name = subject_info[2]
    labels_exist = os.path.exists(os.path.join(subject_path,
                                  subject_name + '_labels.npz'))
    target_exists = os.path.exists(os.path.join(subject_path, 'target.npz'))
    X_exists = os.path.exists(os.path.join(subject_path, 'X.csv'))
    lf_exists = os.path.exists(os.path.join(subject_path, 'lead_field.npz'))

    if not (labels_exist and target_exists and X_exists and lf_exists):
        print('skipping {}. not all the necessary files are present'.format(
              subject_path))
        continue

    print('adding subject ' + subject_name)
    subject_data = pd.read_csv(os.path.join(subject_path, 'X.csv'))
    subject_data['subject'] = subject_name
    target_subject = sparse.load_npz(os.path.join(subject_path, 'target.npz'))

    if sbj_id == 0:
        # create new .csv file
        subject_data.to_csv(all_X_file, header=True, index=False)
        target_all = target_subject
    else:
        # append the data
        subject_data.to_csv(all_X_file, mode='a', header=False, index=False)
        target_all = sparse.vstack((target_all, target_subject))
    # shutil.copyfile(os.path.join(subject_path, 'labels.pickle'),
    #                os.path.join(data_dir_all, subject_name + '_labels.pickle')
    #                )
    shutil.copyfile(os.path.join(subject_path, 'lead_field.npz'),
                    os.path.join(data_dir_all,
                                 subject_name + '_lead_field.npz')
                    )
    shutil.copyfile(os.path.join(subject_path, subject_name + '_labels.npz'),
                    os.path.join(data_dir_all,
                                 subject_name + '_labels.npz')
                    )
    sbj_id += 1

# save the target
save_npz(os.path.join(data_dir_all, 'target.npz'), target_all)
print('{} samples from {} subjects were saved in the {}'.format(
      target_all.shape[0], sbj_id, data_dir_all))
