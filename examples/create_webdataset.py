import webdataset
from webdataset.writer import TarWriter, ShardWriter
import pickle
import numpy as np
import os.path as osp
import os
import pickle
import numpy as np
from zlib import crc32
import pkg_resources as res
from functools import partial


from multiprocessing import Pool, Manager

import torch
from torch_geometric.data import Dataset
from torch_geometric.data import Data

from photon_stream.representations import (
    list_of_lists_to_raw_phs,
    raw_phs_to_point_cloud,
)
from photon_stream.geometry import GEOMETRY
import photon_stream as ps
import random

from factnn.utils.augment import euclidean_distance, true_sign


# Function to check test set's identifier.
def test_set_check(identifier, test_ratio):
    return crc32(np.int64(identifier)) & 0xFFFFFFFF < test_ratio * 2 ** 32


# Function to split train/test
def split_train_test_by_id(data, test_ratio):
    in_test_set = np.asarray(
        [test_set_check(crc32(str(x).encode()), test_ratio) for x in data]
    )
    return data[~in_test_set], data[in_test_set]


def split_data(paths, val_split=0.2, test_split=0.2):
    """
    Split up the data and return which images should go to which train, test, val directory
    :param paths: The paths to do the splitting on
    :param test_split: Fraction of the data for the test set. the validation set is rolled into the test set.
    :param val_split: Fraction of data in validation set
    :return: A dict containing which images go to which directory
    """

    print(len(paths))
    train, test = split_train_test_by_id(np.asarray(paths), val_split + test_split)
    val, test = split_train_test_by_id(test, val_split)
    print(train.shape)
    print(val.shape)
    print(test.shape)
    return {
        "train": train,
        "val": val,
        "trainval": np.concatenate((train, val)),
        "test": test,
        "all": np.concatenate((train, val, test)),
    }


def write_dataset(base="/run/media/bieker/T7/", split="train"):
    num = 20
    uncleaned = "/run/media/bieker/T7/gamma/no_clean/raw/"
    core = f"/run/media/bieker/T7/gamma/core{num}/raw/"
    clump = f"/run/media/bieker/T7/gamma/clump{num}/raw/"
    puncleaned = "/run/media/bieker/T7/proton/no_clean/raw/"
    pcore = f"/run/media/bieker/T7/proton/core{num}/raw/"
    pclump = f"/run/media/bieker/T7/proton/clump{num}/raw/"
    num_examples_per_shard = 20000
    max_size = 1e10

    event_dict = pickle.load(  # Only need one
        open(
            res.resource_filename(
                "factnn.data.resources", f"core{num}_raw_names.p"
            ),
            "rb",
        )
    )

    raw_names = list(event_dict["proton"]) + list(event_dict["gamma"])
    random.shuffle(raw_names)
    used_paths = split_data(raw_names)[split]

    pattern = os.path.join(base, f"fact-{split}-{num}-%07d.tar")

    with ShardWriter(pattern, maxcount=num_examples_per_shard) as sink:
        for p in used_paths:
            if os.path.exists(os.path.join(core, p)):
                raw_path = os.path.join(core, p)
                clump_path = os.path.join(clump, p)
                uncleaned_path = os.path.join(uncleaned, p)
                is_gamma = True
            elif os.path.exists(os.path.join(pcore, p)):
                raw_path = os.path.join(pcore, p)
                clump_path = os.path.join(pclump, p)
                uncleaned_path = os.path.join(puncleaned, p)
                is_gamma = False
            try:
                with open(raw_path, "rb") as pickled_event:
                    with open(uncleaned_path, "rb") as pickled_original:
                        (
                            event_data,
                            data_format,
                            features,
                            feature_cluster,
                        ) = pickle.load(pickled_event)
                        uncleaned_data, _, _, _ = pickle.load(pickled_original)
                        uncleaned_photons = uncleaned_data[data_format["Image"]]
                        uncleaned_photons = list_of_lists_to_raw_phs(uncleaned_photons)
                        uncleaned_cloud = np.asarray(
                            raw_phs_to_point_cloud(
                                uncleaned_photons,
                                cx=GEOMETRY.x_angle,
                                cy=GEOMETRY.y_angle,
                            )
                        )
                        # Convert List of List to Point Cloud
                        event_photons = event_data[data_format["Image"]]
                        event_photons = list_of_lists_to_raw_phs(event_photons)
                        point_cloud = np.asarray(
                            raw_phs_to_point_cloud(
                                event_photons, cx=GEOMETRY.x_angle, cy=GEOMETRY.y_angle
                            )
                        )
                        out = np.where(
                            (uncleaned_cloud == point_cloud[:, None]).all(-1)
                        )[1]
                        point_values = np.zeros(uncleaned_cloud.shape)
                        point_values[out] = 1

                        with open(clump_path, "rb") as pickled_clump:
                            clump_data, _, _, _ = pickle.load(pickled_clump)
                            clump_photons = clump_data[data_format["Image"]]
                            clump_photons = list_of_lists_to_raw_phs(clump_photons)
                            clump_cloud = np.asarray(
                                raw_phs_to_point_cloud(
                                    clump_photons,
                                    cx=GEOMETRY.x_angle,
                                    cy=GEOMETRY.y_angle,
                                )
                            )
                            out = np.where(
                                (uncleaned_cloud == clump_cloud[:, None]).all(-1)
                            )[1]
                            clump_values = np.zeros(uncleaned_cloud.shape)
                            clump_values[out] = 1
                            # clump_values = np.isclose(clump_cloud, point_cloud)
                            # Convert to ints so that addition works, gives 0 for outside, 1 clump, 2 core
                            point_values = point_values.astype(
                                int
                            ) + clump_values.astype(int)
                            point_values = point_values[:, 0]
                        energy = np.array(
                            [event_data[data_format["Energy"]]],
                            dtype=np.long,
                        )
                        phi = np.array(
                            [event_data[4]],
                            dtype=np.long,  # Needed because most the proton events had the wrong data_format
                        )
                        theta = np.array(
                            [event_data[5]],
                            dtype=np.long,  # Needed because most the proton events had the wrong data_format
                        )
                        # Now add the features from the feature extraction
                        if (
                                features["extraction"] == 1
                        ):  # Failed extraction, so has no features to use
                            feature_list = []
                        else:
                            feature_list = []
                            feature_list.append(features["head_tail_ratio"])
                            feature_list.append(features["length"])
                            feature_list.append(features["width"])
                            feature_list.append(features["time_gradient"])
                            feature_list.append(features["number_photons"])
                            feature_list.append(
                                features["length"] * features["width"] * np.pi
                            )
                            feature_list.append(
                                (
                                        (features["length"] * features["width"] * np.pi)
                                        / np.log(features["number_photons"]) ** 2
                                )
                            )
                            feature_list.append(
                                (
                                        features["number_photons"]
                                        / (features["length"] * features["width"] * np.pi)
                                )
                            )
                        if is_gamma:
                            try:
                                # Try Diffuse
                                disp = np.array(
                                    [true_sign(
                                        event_data[data_format["Source_X"]],
                                        event_data[data_format["Source_Y"]],
                                        event_data[data_format["COG_X"]],
                                        event_data[data_format["COG_Y"]],
                                        event_data[data_format["Delta"]],
                                    )
                                     * euclidean_distance(
                                        event_data[data_format["Source_X"]],
                                        event_data[data_format["Source_Y"]],
                                        event_data[data_format["COG_X"]],
                                        event_data[data_format["COG_Y"]],
                                    )],
                                    dtype=np.float,
                                )
                            except:
                                disp = None
                        else:
                            disp = None
                        points = torch.tensor(uncleaned_cloud, dtype=torch.float).squeeze().numpy()
                        print(f"Points: {points.shape}, Points Mask: {point_values.shape}, Values: Min: {np.min(point_values)} Max: {np.max(point_values)} Values: {np.unique(point_values)}")
                        sample = {"__key__": p, "points.pyd": points, "mask.pyd": point_values,
                                  "features.pyd": np.asarray(feature_list, dtype=np.float), "disp.pyd": disp,
                                  "energy.pyd": energy, "theta.pyd": theta, "phi.pyd": phi, "class.pyd": is_gamma}
                        sink.write(sample)
            except Exception as e:
                print(f"Failed: {e}")


write_dataset()
write_dataset(split="val")
write_dataset(split="test")
