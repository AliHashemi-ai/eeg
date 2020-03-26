import os
import numpy as np
import pandas as pd
import pickle
# import matplotlib.pyplot as plt

from scipy import sparse
from sklearn.multioutput import MultiOutputClassifier
from sklearn.neighbors import KNeighborsClassifier

from simulation.lead_correlate import LeadCorrelate
import simulation.metrics as met

# Load train data
# X_train = pd.read_csv(os.path.join('data', 'train.csv'))
# y_train = sparse.load_npz(os.path.join('data', 'train_target.npz')).toarray()

'''
# Visualize
if 0:
    import mne  # noqa
    fig_dir = 'figs'
    if not os.path.isdir(fig_dir):
        os.mkdir(fig_dir)

    data_path = mne.datasets.sample.data_path()
    fname = data_path + '/MEG/sample/sample_audvis-ave.fif'
    info = mne.read_evokeds(fname)[0].pick('eeg').info
    n_classes = y_train.shape[1]
    fig, axes = plt.subplots(5, n_classes, figsize=(16, 4))

    for k in range(n_classes):
        X_k = X_train.iloc[np.argmax(y_train, axis=1) == k]
        for i, ax in enumerate(axes[:, k]):
            mne.viz.plot_topomap(X_k.iloc[i].values, info, axes=ax)
    plt.tight_layout()
    plt.save(os.path.join(fig_dir, 'visualize.png'))
    plt.show()
'''

clf = KNeighborsClassifier(3)
model = MultiOutputClassifier(clf, n_jobs=-1)
# model.fit(X_train, y_train)

# Load test data
# X_test = pd.read_csv(os.path.join('data', 'test.csv'))
# y_test = sparse.load_npz(os.path.join('data', 'test_target.npz')).toarray()
# print(model.score(X_test, y_test))

data_samples = np.logspace(1, 4, num=10, base=10, dtype='int')

# check for all the data directories
'''
import glob
scores_all = {}
for data_dir in os.listdir('.'):
    if data_dir[:4] == 'data':
        scores = []
        print('working on %s' % (data_dir))
        no_parcels = int(data_dir[5:])

        X_train = pd.read_csv(os.path.join(data_dir, 'train.csv'))
        y_train = sparse.load_npz(os.path.join(data_dir,
                                            'train_target.npz')).toarray()
        X_test = pd.read_csv(os.path.join(data_dir, 'test.csv'))
        y_test = sparse.load_npz(os.path.join(data_dir,
                                 'test_target.npz')).toarray()

        for no_samples in data_samples[data_samples < 4641]: #len(X_train)]:
            no_samples_test = int(no_samples * 0.2)
            model.fit(X_train.head(no_samples),
                                   y_train[:no_samples])
            score = model.score(X_test.head(no_samples_test),
                                             y_test[:no_samples_test])
            scores.append(score)
        scores_all[str(no_parcels)] = scores

import matplotlib.pylab as plt
plt.figure()

for s in scores_all.keys():
    plt.plot(data_samples[:len(scores_all[s])], scores_all[s],
             label = s + ' parcels')
plt.legend()
plt.xlabel('number of samples used')
plt.ylabel('score (on Kneighours)')
plt.savefig('score.png')
'''

y_test_score = []
y_train_score = []
max_parcels_all = []
for data_dir in os.listdir('.'):
    if 'data_15_3' in data_dir:
        max_parcels = data_dir[8:]
        L = np.load(os.path.join(data_dir, 'lead_field.npz'))
        L = L['arr_0']

        X_train = pd.read_csv(os.path.join(data_dir, 'train.csv'))
        y_train = sparse.load_npz(os.path.join(data_dir,
                                  'train_target.npz')).toarray()
        X_test = pd.read_csv(os.path.join(data_dir, 'test.csv'))
        y_test = sparse.load_npz(os.path.join(data_dir,
                                 'test_target.npz')).toarray()

        with open(os.path.join(data_dir, 'labels.pickle'), 'rb') as outfile:
            labels = pickle.load(outfile)

        # reading forward matrix and saving
        import mne
        data_path = mne.datasets.sample.data_path()
        subject = 'sample'
        fwd_fname = os.path.join(data_path, 'MEG', subject,
                                 subject + '_audvis-meg-eeg-oct-6-fwd.fif')
        fwd = mne.read_forward_solution(fwd_fname)
        fwd = mne.convert_forward_solution(fwd, force_fixed=True)
        lead_field = fwd['sol']['data']

        # now we make a vector of size n_vertices for each surface of cortex
        # hemisphere and put a int for each vertex that says it which label
        # it belongs to.
        parcel_indices_lh = np.zeros(len(fwd['src'][0]['inuse']), dtype=int)
        parcel_indices_rh = np.zeros(len(fwd['src'][1]['inuse']), dtype=int)
        for label_name, label_idx in labels.items():
            label_id = int(label_name[:-3])
            if '-lh' in label_name:
                parcel_indices_lh[label_idx] = label_id
            else:
                parcel_indices_rh[label_idx] = label_id

        # Make sure label numbers different for each hemisphere
        parcel_indices = np.concatenate((parcel_indices_lh,
                                        parcel_indices_rh), axis=0)

        # Now pick vertices that are actually used in the forward
        inuse = np.concatenate((fwd['src'][0]['inuse'],
                                fwd['src'][1]['inuse']), axis=0)

        parcel_indices_leadfield = parcel_indices[np.where(inuse)[0]]

        assert len(parcel_indices_leadfield) == L.shape[1]

        lc = LeadCorrelate(L, parcel_indices_leadfield)
        lc.fit(X_train, y_train)
        y_pred1 = lc.predict(X_test)
        y_pred2 = lc.predict(X_train)
        # plotFROC()

        # y_pred = lc.predict(X_train)
        # y_pred2 = lc.predict(X_test)

        # score_test = lc.score(X_test, y_test)
        # score_train = lc.score(X_train, y_train)

        # calculating
        from sklearn.metrics import hamming_loss
        hl = hamming_loss(y_test, y_pred1)

        from sklearn.metrics import jaccard_score
        js = jaccard_score(y_test, y_pred1, average='samples')
        print('score: hamming: {:.2f}, jaccard: {:.2f}'.format(hl, js))

        from sklearn.model_selection import cross_val_score

        lc2 = LeadCorrelate(L, parcel_indices_leadfield)
        cross_val = cross_val_score(lc2, X_train, y_train, cv=3)
        print('cross validation (smaller the better): {}'.format(cross_val))

        from sklearn.metrics import make_scorer
        scorer_froc = make_scorer(met.froc_score, needs_proba=True)
        scorer_afroc = make_scorer(met.afroc_score, needs_proba=True)
        cross_val_score(lc2, X_train, y_train, cv=3)

        froc = met.froc_score(X_test, y_test)
        area = met.calc_froc_area(X_test, y_test)

        # y_test_score.append(score_test)
        # y_train_score.append(score_train)
        # max_parcels_all.append(max_parcels)

        '''
        Partial area measures, such as the areaunder the FROC curve to the left
        of a predefined abscissa value or the value of the ordinateat the
        predefined abscissa have been used as figures of merit.

        The AFROC curve and associated figure of merit—Bunch et al [4] also
        introducedthe plot of LLF vs. false positive fraction (FPF) which was
        subsequently termed thealternative FROC (AFROC) by the author [10].
        Since the AFROC curve is completelycontained within the unit square,
        since both axes are probabilities, the author suggested that,analogous
        to the area under the ROC curve, the area under the AFROC be used as a
        figure-of-merit for FROC performance

        '''

'''
plt.figure()
plt.plot(max_parcels_all, y_test_score, 'ro')
plt.plot(max_parcels_all, y_train_score, 'ro')
plt.xlabel('max parcels')
plt.ylabel('score (avg #errors/sample/max parcels): higher is worse')

plt.title('Results for 15 parcels')
plt.show()
'''
