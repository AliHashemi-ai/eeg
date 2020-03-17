import os.path as op
import os

import numpy as np
import pandas as pd
# import pickle
# import random
from scipy.sparse import csr_matrix
from scipy.sparse import save_npz

import mne
from mne.utils import check_random_state

from joblib import Memory, Parallel, delayed
from tqdm import tqdm

from simulation.parcels import find_centers_of_mass
from simulation.raw_signal import generate_signal
from simulation.parcels import make_random_parcellation
# from simulation.plot_signal import visualize_brain

# IMPORTANT: run it with ipython --gui=qt


mem = Memory('./')
N_JOBS = -1
# N_JOBS = 1

make_random_parcellation = mem.cache(make_random_parcellation)


@mem.cache
def prepare_parcels(subject, subjects_dir, hemi, n_parcels, random_state):
    if ((hemi == 'both') or (hemi == 'lh')):
        annot_fname_lh = 'lh.random' + str(n_parcels) + '.annot'
        annot_fname_lh = op.join(subjects_dir, subject, 'label',
                                 annot_fname_lh)
    if ((hemi == 'both') or (hemi == 'rh')):
        annot_fname_rh = 'rh.random' + str(n_parcels) + '.annot'
        annot_fname_rh = op.join(subjects_dir, subject, 'label',
                                 annot_fname_rh)

    make_random_parcellation(annot_fname_lh, n_parcels,
                             'lh', subjects_dir,
                             random_state, subject,
                             remove_corpus_callosum=True)

    make_random_parcellation(annot_fname_rh, n_parcels, 'rh',
                             subjects_dir,
                             random_state, subject,
                             remove_corpus_callosum=True)

    # read the labels from annot
    if ((hemi == 'both') or (hemi == 'lh')):
        parcels_lh = mne.read_labels_from_annot(subject=subject,
                                                annot_fname=annot_fname_lh,
                                                hemi='lh',
                                                subjects_dir=subjects_dir)
        cm_lh = find_centers_of_mass(parcels_lh, subjects_dir)
        # remove the last, unknown label which is corpus callosum
        assert parcels_lh[-1].name[:7] == 'unknown'
        parcels_lh = parcels_lh[:-1]
    if ((hemi == 'both') or (hemi == 'rh')):
        parcels_rh = mne.read_labels_from_annot(subject=subject,
                                                annot_fname=annot_fname_rh,
                                                hemi='rh',
                                                subjects_dir=subjects_dir)
        # remove the last, unknown label which is corpus callosum
        assert parcels_rh[-1].name[:7] == 'unknown'
        parcels_rh = parcels_rh[:-1]
        cm_rh = find_centers_of_mass(parcels_rh, subjects_dir)

    if hemi == 'both':
        return [parcels_lh, parcels_rh], [cm_lh, cm_rh]
    elif hemi == 'rh':
        return [parcels_rh], [cm_rh]
    elif hemi == 'lh':
        return [parcels_lh], [cm_lh]


# @mem.cache
def init_signal(parcels, cms, hemi, n_parcels_max=3, random_state=None):
    # randomly choose how many parcels will be activated, left or right
    # hemisphere and exact parcels
    rng = check_random_state(random_state)

    if hemi == 'both':
        parcels_lh, parcels_rh = parcels
        cm_lh, cm_rh = cms
    elif hemi == 'rh':
        [parcels_rh] = parcels
        [cm_rh] = cms
    elif hemi == 'lh':
        [parcels_lh] = parcels
        [cm_lh] = cms

    n_parcels = rng.randint(n_parcels_max, size=1)[0] + 1
    to_activate = []
    parcels_selected = []

    # do this so that the same label is not selected twice
    deck_lh = list(rng.permutation(len(parcels_lh)))
    deck_rh = list(rng.permutation(len(parcels_rh)))
    for idx in range(n_parcels):
        if hemi == 'both':
            hemi_selected = ['lh', 'rh'][rng.randint(2, size=1)[0]]
        else:
            hemi_selected = hemi

        if hemi_selected == 'lh':
            parcel_selected = deck_lh.pop()
            l1_center_of_mass = parcels_lh[parcel_selected].copy()
            l1_center_of_mass.vertices = [cm_lh[parcel_selected]]
            parcel_used = parcels_lh[parcel_selected]
        elif hemi_selected == 'rh':
            parcel_selected = deck_rh.pop()
            l1_center_of_mass = parcels_rh[parcel_selected].copy()
            l1_center_of_mass.vertices = [cm_rh[parcel_selected]]
            parcel_used = parcels_rh[parcel_selected]
        to_activate.append(l1_center_of_mass)
        parcels_selected.append(parcel_used)

    # activate selected parcels
    data = 0.
    for idx in range(n_parcels):
        events, _, raw = generate_signal(data_path, subject,
                                         parcels=to_activate)
        evoked = mne.Epochs(raw, events, tmax=0.3).average()
        data = data + evoked.data[:, np.argmax((evoked.data ** 2).sum(axis=0))]

    # visualize_brain(subject, hemi, 'random' + str(n), subjects_dir,
    #                parcels_selected)

    names_parcels_selected = [parcel.name for parcel in parcels_selected]
    return data, names_parcels_selected


def targets_to_sparse(target_list, parcel_names):
    targets = []

    for idx, tar in enumerate(target_list):
        row = np.zeros(len(parcel_names))
        for t in tar:
            row[np.where(parcel_names == t)[0][0]] = 1
        targets.append(row)
    targets_sparse = csr_matrix(targets)
    return targets_sparse


# same variables
n_parcels = 10  # number of parcels per hemisphere (without corpus callosum)
random_state = 10
hemi = 'both'
subject = 'sample'
recalculate_parcels = True  # initiate new random parcels
n_samples_train = 20
n_samples_test = 3
n_parcels_max = 1

# Here we are creating the directories/files for left and right hemisphere
data_path = mne.datasets.sample.data_path()
subjects_dir = op.join(data_path, 'subjects')

parcels, cms = prepare_parcels(subject, subjects_dir, hemi=hemi,
                               n_parcels=n_parcels,
                               random_state=42)
parcels_flat = [item for sublist in parcels for item in sublist]
parcel_names = [parcel.name for parcel in parcels_flat]
parcel_names = np.array(parcel_names)

# save label names with their corresponding vertices
parcel_vertices = {}
for parcel in parcels_flat:
    parcel_vertices[parcel.name] = parcel.vertices

# prepare train and test data
signal_list = []
target_list = []
rng = np.random.RandomState(42)
n_samples = n_samples_train + n_samples_test
seeds = rng.randint(np.iinfo('int32').max, size=n_samples)


train_data = Parallel(n_jobs=N_JOBS, backend='multiprocessing')(
    delayed(init_signal)(parcels, cms, hemi, n_parcels_max, seed)
    for seed in tqdm(seeds)
)

signal_list, target_list = zip(*train_data)

signal_list = np.array(signal_list)
data_labels = ['e%d' % (idx + 1) for idx in range(signal_list.shape[1])]
df = pd.DataFrame(signal_list, columns=list(data_labels))
target = targets_to_sparse(target_list, parcel_names)

df_train = df.iloc[:n_samples_train]
train_target = target[:n_samples_train]

df_test = df.iloc[n_samples_train:]
test_target = target[n_samples_train:]

if not os.path.isdir('data/'):
    os.mkdir('data/')

df_train.to_csv('data/train.csv', index=False)
save_npz('data/train_target.npz', train_target)
print(str(len(df_train)), ' train samples were saved')

df_test.to_csv('data/test.csv', index=False)
save_npz('data/test_target.npz', test_target)
print(str(len(df_test)), ' test samples were saved')

# Visualize
fname = data_path + '/MEG/sample/sample_audvis-ave.fif'
info = mne.read_evokeds(fname)[0].pick('eeg').info
evoked = mne.EvokedArray(df.values.T, info, tmin=0)
evoked.plot_topomap()

# data to give to the participants:
# labels with their names and vertices: parcels
# ? centers of mass: cms
# datapoints generated along with the target labels: df
