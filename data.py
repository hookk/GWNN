import numpy as np
import scipy.sparse as sp
import math
import pickle as pkl
from sklearn.preprocessing import normalize
from scipy.sparse.linalg.eigen.arpack import eigsh
from scipy.special import iv
from scipy.integrate import quad
import sys

def parse_index_file(filename):
	"""Parse index file."""
	index = []
	for line in open(filename):
		index.append(int(line.strip()))
	return index


def sample_mask(idx, l):
	"""Create mask."""
	mask = np.zeros(l)
	mask[idx] = 1
	return np.array(mask, dtype=np.bool)

def load_data(dataset_str):
	"""
	Loads input data from gcn/data directory

	ind.dataset_str.x => the feature vectors of the training instances as scipy.sparse.csr.csr_matrix object;
	ind.dataset_str.tx => the feature vectors of the test instances as scipy.sparse.csr.csr_matrix object;
	ind.dataset_str.allx => the feature vectors of both labeled and unlabeled training instances
		(a superset of ind.dataset_str.x) as scipy.sparse.csr.csr_matrix object;
	ind.dataset_str.y => the one-hot labels of the labeled training instances as numpy.ndarray object;
	ind.dataset_str.ty => the one-hot labels of the test instances as numpy.ndarray object;
	ind.dataset_str.ally => the labels for instances in ind.dataset_str.allx as numpy.ndarray object;
	ind.dataset_str.graph => a dict in the format {index: [index_of_neighbor_nodes]} as collections.defaultdict
		object;
	ind.dataset_str.test.index => the indices of test instances in graph, for the inductive setting as list object.

	All objects above must be saved using python pickle module.

	:param dataset_str: Dataset name
	:return: All data input files loaded (as well the training/test data).
	"""
	names = ['x', 'y', 'tx', 'ty', 'allx', 'ally', 'graph']
	objects = []
	for i in range(len(names)):
		with open("data/ind.{}.{}".format(dataset_str, names[i]), 'rb') as f:
			if sys.version_info > (3, 0):
				objects.append(pkl.load(f, encoding='latin1'))
			else:
				objects.append(pkl.load(f))

	x, y, tx, ty, allx, ally, graph = tuple(objects)
	test_idx_reorder = parse_index_file("data/ind.{}.test.index".format(dataset_str))
	test_idx_range = np.sort(test_idx_reorder)

	if dataset_str == 'citeseer':
		# Fix citeseer dataset (there are some isolated nodes in the graph)
		# Find isolated nodes, add them as zero-vecs into the right position
		test_idx_range_full = range(min(test_idx_reorder), max(test_idx_reorder)+1)
		tx_extended = sp.lil_matrix((len(test_idx_range_full), x.shape[1]))
		tx_extended[test_idx_range-min(test_idx_range), :] = tx
		tx = tx_extended
		ty_extended = np.zeros((len(test_idx_range_full), y.shape[1]))
		ty_extended[test_idx_range-min(test_idx_range), :] = ty
		ty = ty_extended

	features = sp.vstack((allx, tx)).tolil()
	features[test_idx_reorder, :] = features[test_idx_range, :]
	adj = nx.adjacency_matrix(nx.from_dict_of_lists(graph))

	labels = np.vstack((ally, ty))
	labels[test_idx_reorder, :] = labels[test_idx_range, :]

	classes_num = labels.shape[1]

	isolated_list = [i for i in range(labels.shape[0]) if np.all(labels[i] == 0)]
	if isolated_list:
		print(f"Warning: Dataset '{dataset_str}' contains {len(isolated_list)} isolated nodes")

	labels = np.array([np.argmax(row) for row in labels], dtype=np.long)

	idx_test = test_idx_range.tolist()
	idx_train = range(len(y))
	idx_val = range(len(y), len(y)+500)

	train_mask = sample_mask(idx_train, labels.shape[0])
	val_mask = sample_mask(idx_val, labels.shape[0])
	test_mask = sample_mask(idx_test, labels.shape[0])

	y_train = labels[train_mask]
	y_val = labels[val_mask]
	y_test = labels[test_mask]

	return adj, features, y_train, y_val, y_test, classes_num, train_mask, val_mask, test_mask

def preprocess_features(features):
    """Row-normalize feature matrix and convert to tuple representation"""
    rowsum = np.array(features.sum(1))
    # print rowsum
    r_inv = np.power(rowsum, -1).flatten()
    r_inv[np.isinf(r_inv)] = 0.
    r_mat_inv = sp.diags(r_inv,0)
    features = r_mat_inv.dot(features)
    return features