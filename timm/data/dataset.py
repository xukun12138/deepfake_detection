from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import torch.utils.data as data

import os
import re
import torch
import tarfile
from PIL import Image
import random
import numpy as np

IMG_EXTENSIONS = ['.png', '.jpg', '.jpeg']


def natural_key(string_):
    """See http://www.codinghorror.com/blog/archives/001018.html"""
    return [int(s) if s.isdigit() else s for s in re.split(r'(\d+)', string_.lower())]


def find_images_and_targets(folder, types=IMG_EXTENSIONS, class_to_idx=None, leaf_name_only=True, sort=True):
    labels = []
    filenames = []
    for root, subdirs, files in os.walk(folder, topdown=False):
        rel_path = os.path.relpath(root, folder) if (root != folder) else ''
        label = os.path.basename(rel_path) if leaf_name_only else rel_path.replace(os.path.sep, '_')
        for f in files:
            base, ext = os.path.splitext(f)
            if ext.lower() in types:
                filenames.append(os.path.join(root, f))
                labels.append(label)
    if class_to_idx is None:
        # building class index
        unique_labels = set(labels)
        sorted_labels = list(sorted(unique_labels, key=natural_key))
        class_to_idx = {c: idx for idx, c in enumerate(sorted_labels)}
    images_and_targets = zip(filenames, [class_to_idx[l] for l in labels])
    if sort:
        images_and_targets = sorted(images_and_targets, key=lambda k: natural_key(k[0]))
    return images_and_targets, class_to_idx


def find_images_and_targets_v1(folder, class_to_idx=None, leaf_name_only=True):
    labels = []

    for root, subdirs, files in os.walk(folder, topdown=False):
        rel_path = os.path.relpath(root, folder) if (root != folder) else ''
        label = os.path.basename(rel_path) if leaf_name_only else rel_path.replace(os.path.sep, '_')
        if label == '' or label[0] == '.':
            continue
        labels.append(label)
    if class_to_idx is None:
        # building class index
        unique_labels = set(labels)
        sorted_labels = list(sorted(unique_labels, key=natural_key))
        class_to_idx = {c: idx for idx, c in enumerate(sorted_labels)}
    return class_to_idx


def load_class_map(filename, root=''):
    class_to_idx = {}
    class_map_path = filename
    if not os.path.exists(class_map_path):
        class_map_path = os.path.join(root, filename)
        assert os.path.exists(class_map_path), 'Cannot locate specified class map file (%s)' % filename
    class_map_ext = os.path.splitext(filename)[-1].lower()
    if class_map_ext == '.txt':
        with open(class_map_path) as f:
            class_to_idx = {v.strip(): k for k, v in enumerate(f)}
    else:
        assert False, 'Unsupported class map extension'
    return class_to_idx


class Dataset(data.Dataset):

    def __init__(
            self,
            root,
            load_bytes=False,
            transform=None,
            class_map=''):

        class_to_idx = None
        if class_map:
            class_to_idx = load_class_map(class_map, root)
        images, class_to_idx = find_images_and_targets(root, class_to_idx=class_to_idx)

        if len(images) == 0:
            raise (RuntimeError("Found 0 images in subfolders of: " + root + "\n"
                                                                             "Supported image extensions are: " + ",".join(
                IMG_EXTENSIONS)))
        self.root = root
        self.samples = images
        self.imgs = self.samples  # torchvision ImageFolder compat
        self.class_to_idx = class_to_idx
        self.load_bytes = load_bytes
        self.transform = transform

    def __getitem__(self, index):
        path, target = self.samples[index]
        img = open(path, 'rb').read() if self.load_bytes else Image.open(path).convert('RGB')
        if self.transform is not None:
            img = self.transform(img)
        if target is None:
            target = torch.zeros(1).long()
        return img, target

    def __len__(self):
        return len(self.imgs)

    def filenames(self, indices=[], basename=False):
        if indices:
            if basename:
                return [os.path.basename(self.samples[i][0]) for i in indices]
            else:
                return [self.samples[i][0] for i in indices]
        else:
            if basename:
                return [os.path.basename(x[0]) for x in self.samples]
            else:
                return [x[0] for x in self.samples]


class DeepFakeDataset_v1_bak(data.Dataset):
    def __init__(
            self,
            root,
            result_file,
            load_bytes=False,
            transform=None,
            transform_rotateds=None,
            class_map=''):

        class_to_idx = None
        if class_map:
            class_to_idx = load_class_map(class_map, root)
        class_to_idx = find_images_and_targets_v1(root, class_to_idx=class_to_idx)
        self.root = root
        self.class_to_idx = class_to_idx
        self.load_bytes = load_bytes
        self.transform = transform
        self.transform_rotateds = transform_rotateds

        self.results_fake = []
        self.results_real = []

        self.results = []

        with open(result_file, 'r') as f:
            lines = f.readlines()
            for line in lines:
                line_s = line.strip().split(':')
                if len(line_s) != 3:
                    continue
                self.results_fake.append((line_s[0], int(line_s[2])))  # fake,rotated
                self.results_real.append((line_s[1], int(line_s[2])))  # real,rotated
                self.results.append((line_s[0], int(line_s[2]), 0))  # fake,rotated, label
                self.results.append((line_s[1], int(line_s[2]), 1))  # real,rotated, label

        if len(self.results) == 0:
            raise (RuntimeError("Found 0 images in subfolders of: " + root + "\n"
                                                                             "Supported image extensions are: " + ",".join(
                IMG_EXTENSIONS)))
        import random
        random.shuffle(self.results_real)
        random.shuffle(self.results)

    def __getitem__(self, index):
        fake_path, fake_rotated = self.results_fake[index]
        real_path, real_rotated = self.results_real[index]

        fake_img = open(fake_path, 'rb').read() if self.load_bytes else Image.open(fake_path).convert('RGB')
        real_img = open(real_path, 'rb').read() if self.load_bytes else Image.open(real_path).convert('RGB')

        if self.transform_rotateds is not None:
            fake_img = self.transform_rotateds[fake_rotated](fake_img)
            real_img = self.transform_rotateds[real_rotated](real_img)

        if self.transform is not None:
            fake_img = self.transform(fake_img)
            real_img = self.transform(real_img)
        if fake_rotated is None:
            fake_rotated = torch.zeros(1).long()
        if real_rotated is None:
            real_rotated = torch.zeros(1).long()
        return fake_img, real_img, fake_rotated, real_rotated

    def __len__(self):
        return len(self.results_fake)


def get_all_files(input_dir, suffix=None):
    files = []
    for file in os.listdir(input_dir):
        file_path = os.path.join(input_dir, file)
        if os.path.isfile(file_path) and (suffix is None or os.path.splitext(file_path)[1] == suffix):
            files.append(file_path)
    return files


def get_all_images(datadirs):
    results = []
    for dir_now in datadirs:
        results += get_all_files(dir_now, '.jpg')
    return results


def load_class_map_v2(class_names):
    class_names = [name.strip() for name in class_names.split(',')]
    class_to_idx = {class_name: index for index, class_name in enumerate(class_names)}
    return class_to_idx


def get_all_images_list(list_files):
    files = []
    for root_index, list_file in enumerate(list_files):
        if not os.path.isfile(list_file):
            continue
        with open(list_file, 'r') as f:
            files += [(line.strip(), root_index) for line in f.readlines()]
    return files


class DatasetTar(data.Dataset):

    def __init__(self, root, load_bytes=False, transform=None, class_map=''):

        class_to_idx = None
        if class_map:
            class_to_idx = load_class_map(class_map, root)
        assert os.path.isfile(root)
        self.root = root
        with tarfile.open(root) as tf:  # cannot keep this open across processes, reopen later
            self.samples, self.class_to_idx = _extract_tar_info(tf, class_to_idx)
        self.tarfile = None  # lazy init in __getitem__
        self.load_bytes = load_bytes
        self.transform = transform

    def __getitem__(self, index):
        if self.tarfile is None:
            self.tarfile = tarfile.open(self.root)
        tarinfo, target = self.samples[index]
        iob = self.tarfile.extractfile(tarinfo)
        img = iob.read() if self.load_bytes else Image.open(iob).convert('RGB')
        if self.transform is not None:
            img = self.transform(img)
        if target is None:
            target = torch.zeros(1).long()
        return img, target

    def __len__(self):
        return len(self.samples)


class AugMixDataset(torch.utils.data.Dataset):
    """Dataset wrapper to perform AugMix or other clean/augmentation mixes"""

    def __init__(self, dataset, num_splits=2):
        self.augmentation = None
        self.normalize = None
        self.dataset = dataset
        if self.dataset.transform is not None:
            self._set_transforms(self.dataset.transform)
        self.num_splits = num_splits

    def _set_transforms(self, x):
        assert isinstance(x, (list, tuple)) and len(x) == 3, 'Expecting a tuple/list of 3 transforms'
        self.dataset.transform = x[0]
        self.augmentation = x[1]
        self.normalize = x[2]

    @property
    def transform(self):
        return self.dataset.transform

    @transform.setter
    def transform(self, x):
        self._set_transforms(x)

    def _normalize(self, x):
        return x if self.normalize is None else self.normalize(x)

    def __getitem__(self, i):
        x, y = self.dataset[i]  # all splits share the same dataset base transform
        x_list = [self._normalize(x)]  # first split only normalizes (this is the 'clean' split)
        # run the full augmentation on the remaining splits
        for _ in range(self.num_splits - 1):
            x_list.append(self._normalize(self.augmentation(x)))
        return tuple(x_list), y

    def __len__(self):
        return len(self.dataset)
