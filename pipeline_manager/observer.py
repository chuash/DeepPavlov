# Copyright 2017 Neural Networks and Deep Learning lab, MIPT
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import json
import shutil

from shutil import rmtree
from collections import OrderedDict
from os.path import join, isdir, isfile


class Observer(object):
    """
    The :class:`~pipeline_manager.observer.Observer` implements the functions of observing the course of experiments,
    collecting results, time and other useful information, logging and storing it.
    """
    def __init__(self, name: str, root: str, info: dict, date: str, plot: bool) -> None:
        """
        Initializes the log, creates a folders tree and files necessary for the observer to work.

        Args:
            name: str; name of the experiments.
            root: str; path to root folder.
            info: dict; additional information that you want to add to the log, the content of the dictionary
             does not affect the algorithm
            date: str; date of the experiment.
        """

        self.exp_name = name
        self.exp_inf = info
        self.root = root
        self.date = date
        self.plot = plot

        # tmp parameters
        self.pipe_ind = 0
        self.pipe_conf = None
        self.model = None
        self.pipe_res = None
        self.pipe_time = None
        self.batch_size = None
        self.dataset = None

        # build folder dependencies
        self.save_path = join(self.root, self.date, self.exp_name, 'checkpoints')
        self.log_path = join(self.root, date, self.exp_name)
        self.log_file = join(self.log_path, self.exp_name + '.json')

        if not isdir(self.save_path):
            os.makedirs(self.save_path)
        if self.plot:
            if not isdir(join(self.log_path, 'images')):
                os.makedirs(join(self.log_path, 'images'))

        self.log = OrderedDict(experiment_info=OrderedDict(date=date,
                                                           exp_name=self.exp_name,
                                                           root=self.root,
                                                           info=self.exp_inf,
                                                           number_of_pipes=None,
                                                           metrics=None,
                                                           target_metric=None),
                               experiments=OrderedDict())

    def tmp_reset(self) -> None:
        """
        Reinitialize temporary attributes.
        """
        # tmp parameters
        self.pipe_ind = 0
        self.pipe_conf = None
        self.model = None
        self.pipe_res = None
        self.pipe_time = None
        self.batch_size = None
        self.dataset = None

    def write(self) -> None:
        """
        Write log in log_file.
        """
        if isfile(self.log_file):
            with open(self.log_file, 'r') as old_log:
                old_log = json.load(old_log)

            new_log = self.merge_logs(old_log, self.log)
            with open(self.log_file, 'w') as log_file:
                json.dump(new_log, log_file)
        else:
            with open(self.log_file, 'w') as log_file:
                json.dump(self.log, log_file)

    def exp_time(self, time: str) -> None:
        """
        Adding the time duration of the experiment in log file.

        Args:
            time: the time duration of the experiment

        Returns:
            None
        """
        with open(self.log_file, 'r') as old_log:
            old_log = json.load(old_log)

        old_log['experiment_info']['full_time'] = time
        with open(self.log_file, 'w') as log_file:
            json.dump(old_log, log_file)

    def update_log(self):
        """ Updates a log with new pipeline information. """

        if (self.model is None) and (self.pipe_conf is not None):
            for component in self.pipe_conf:
                if component.get('main') is True:
                    self.model = component['component_name']

        pipe_name = '-->'.join([x['component_name'] for x in self.pipe_conf])

        if self.dataset not in self.log['experiments'].keys():
            self.log['experiments'][self.dataset] = OrderedDict()

        self.log['experiments'][self.dataset][self.pipe_ind] = {'model': self.model,
                                                                'config': self.pipe_conf,
                                                                'light_config': pipe_name,
                                                                'time': self.pipe_time,
                                                                'batch_size': self.batch_size,
                                                                'results': self.pipe_res}

        self.tmp_reset()
        self.write()
        return self

    def save_config(self, conf: dict, dataset_name: str, ind: int) -> None:
        """ Save train config in checkpoint folder. """
        with open(join(self.save_path, dataset_name, "pipe_{}".format(ind), 'config.json'), 'w') as cf:
            json.dump(conf, cf)

    def save_best_pipe(self) -> None:
        """ Calculate the best pipeline and delete others pipelines checkpoints. """
        dataset_res = {}

        with open(self.log_file, 'r') as log_file:
            log = json.load(log_file)

        target_metric = log['experiment_info']['target_metric']

        for dataset_name in log['experiments'].keys():
            for key, item in log['experiments'][dataset_name].items():
                results = item['results']

                if dataset_name not in dataset_res.keys():
                    dataset_res[dataset_name] = dict(best_score=-1, best_ind=None)

                if 'test' in results.keys():
                    if results['test'][target_metric] > dataset_res[dataset_name]["best_score"]:
                        dataset_res[dataset_name]["best_score"] = results['test'][target_metric]
                        dataset_res[dataset_name]["best_ind"] = key

                else:
                    if results['valid'][target_metric] > dataset_res[dataset_name]["best_score"]:
                        dataset_res[dataset_name]["best_score"] = results['valid'][target_metric]
                        dataset_res[dataset_name]["best_ind"] = key

        for name in dataset_res.keys():
            source = join(self.save_path, name)
            dest1 = join(self.save_path, name + '_best_pipe')
            if not os.path.isdir(dest1):
                os.makedirs(dest1)

            files = os.listdir(source)
            for f in files:
                if not f.startswith('pipe') and not os.path.isfile(join(dest1, f)):
                    shutil.move(join(source, f), dest1)
                elif f == 'pipe_{}'.format(dataset_res[name]["best_ind"]):
                    if os.path.isdir(join(dest1, f)):
                        rmtree(join(dest1, f))
                        shutil.move(join(source, f), dest1)
                    else:
                        shutil.move(join(source, f), dest1)

            # del all tmp files in save path
            rmtree(join(self.save_path, name))

    @staticmethod
    def merge_logs(old_log: dict, new_log: dict) -> dict:
        """
        Merge a logs of two experiments.

        Args:
            old_log: config dict
            new_log: config dict

        Returns:
            dict: new config
        """
        n_old = 0
        for dataset_name in old_log['experiments'].keys():
            n_old += len(old_log['experiments'][dataset_name])

        for dataset_name, dataset_val in new_log['experiments'].items():
            if dataset_name not in old_log['experiments'].keys():
                old_log['experiments'][dataset_name] = dataset_val
            else:
                for ind, item in new_log['experiments'][dataset_name].items():
                    if ind not in old_log['experiments'][dataset_name].keys():
                        old_log['experiments'][dataset_name][ind] = item
                    else:
                        for nkey, nval in item.items():
                            match = False
                            for okey, oval in old_log['experiments'][dataset_name][ind].items():
                                if nval['config'] == oval['config']:
                                    match = True
                            if not match:
                                n_old += 1
                                old_log['experiments'][dataset_name][str(n_old)] = nval

        return old_log