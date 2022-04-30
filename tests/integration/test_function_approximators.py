# This file is part of DmpBbo, a set of libraries and programs for the
# black-box optimization of dynamical movement primitives.
# Copyright (C) 2022 Freek Stulp
#
# DmpBbo is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# DmpBbo is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with DmpBbo.  If not, see <http://www.gnu.org/licenses/>.


import argparse
import os
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

import dmpbbo.json_for_cpp as jc
from dmpbbo.functionapproximators.FunctionApproximatorLWR import FunctionApproximatorLWR
from dmpbbo.functionapproximators.FunctionApproximatorRBFN import FunctionApproximatorRBFN
from execute_binary import execute_binary


def plot_comparison(ts, xs, xds, xs_cpp, xds_cpp, fig):
    axs = [fig.add_subplot(2, 2, p + 1) for p in range(4)]

    # plt.rc("text", usetex=True)
    # plt.rc("font", family="serif")

    h_cpp = []
    h_pyt = []
    h_diff = []

    h_pyt.extend(axs[0].plot(ts, xs, label="Python"))
    h_cpp.extend(axs[0].plot(ts, xs_cpp, label="C++"))
    axs[0].set_ylabel("x")

    h_pyt.extend(axs[1].plot(ts, xds, label="Python"))
    h_cpp.extend(axs[1].plot(ts, xds_cpp, label="C++"))
    axs[1].set_ylabel("dx")

    # Reshape needed when xs_cpp has shape (T,)
    h_diff.extend(axs[2].plot(ts, xs - np.reshape(xs_cpp, xs.shape), label="diff"))
    axs[2].set_ylabel("diff x")

    h_diff.extend(axs[3].plot(ts, xds - np.reshape(xds_cpp, xds.shape), label="diff"))
    axs[3].set_ylabel("diff xd")

    plt.setp(h_pyt, linestyle="-", linewidth=4, color=(0.8, 0.8, 0.8))
    plt.setp(h_cpp, linestyle="--", linewidth=2, color=(0.2, 0.2, 0.8))
    plt.setp(h_diff, linestyle="-", linewidth=1, color=(0.8, 0.2, 0.2))

    for ax in axs:
        ax.set_xlabel("$t$")
        ax.legend()

    pass


def target_function(n_samples_per_dim):
    n_dims = 1 if np.isscalar(n_samples_per_dim) else len(n_samples_per_dim)

    if n_dims == 1:
        inputs = np.linspace(0.0, 2.0, n_samples_per_dim)
        targets = 3 * np.exp(-inputs) * np.sin(2 * np.square(inputs))

    else:
        n_samples = np.prod(n_samples_per_dim)
        # Here comes naive inefficient implementation...
        x1s = np.linspace(-2.0, 2.0, n_samples_per_dim[0])
        x2s = np.linspace(-2.0, 2.0, n_samples_per_dim[1])
        inputs = np.zeros((n_samples, n_dims))
        targets = np.zeros(n_samples)
        ii = 0
        for x1 in x1s:
            for x2 in x2s:
                inputs[ii, 0] = x1
                inputs[ii, 1] = x2
                targets[ii] = 2.5 * x1 * np.exp(-np.square(x1) - np.square(x2))
                ii += 1

    return inputs, targets


def train(fa_name, n_dims, save=False):
    directory = "/tmp/testFunctionApproximators/"
    os.makedirs(directory, exist_ok=True)

    # Generate training data
    n_samples_per_dim = 30 if n_dims == 1 else [10, 10]
    (inputs, targets) = target_function(n_samples_per_dim)

    n_rfs = 9 if n_dims == 1 else [5, 5]  # Number of basis functions. To be used later.

    # Initialize function approximator
    if fa_name == "LWR":
        # This value for intersection is quite low. But for the demo it is nice
        # because it makes the linear segments quite obvious.
        intersection = 0.2
        fa = FunctionApproximatorLWR(n_rfs, intersection)
    else:
        intersection = 0.7
        fa = FunctionApproximatorRBFN(n_rfs, intersection)

    # Train function approximator with data
    fa.train(inputs, targets)

    # Make predictions for the targets
    outputs = fa.predict(inputs)  # noqa

    # Make predictions on a grid
    n_samples_per_dim_grid = 200 if n_dims == 1 else [30, 30]
    inputs_grid, _ = target_function(n_samples_per_dim_grid)

    # Save the dynamical system to a json file
    basename = f"{fa_name}_{n_dims}D"
    jc.savejson(Path(directory, f"{basename}.json"), fa)
    jc.savejson_for_cpp(Path(directory, f"{basename}_for_cpp.json"), fa)

    # Save the inputs to a directory
    filename = os.path.join(directory, f"{basename}_inputs.txt")
    np.savetxt(filename, inputs_grid)  # noqa https://youtrack.jetbrains.com/issue/PY-35025

    # Call the binary, which does analytical_solution and integration in C++
    exec_name = "../../bin/testFunctionApproximators"
    arguments = f"{directory} {fa_name} {n_dims}"
    execute_binary(exec_name, arguments)

    outputs_grid_cpp = np.loadtxt(os.path.join(directory, f"{basename}_outputs.txt"))

    h_pyt, ax = fa.plot(inputs, targets=targets)

    if n_dims == 1:
        h_cpp = ax.plot(inputs_grid, outputs_grid_cpp, "-")
    elif n_dims == 2:
        inputs_0_on_grid = np.reshape(inputs_grid[:, 0], n_samples_per_dim_grid)
        inputs_1_on_grid = np.reshape(inputs_grid[:, 1], n_samples_per_dim_grid)
        outputs_on_grid = np.reshape(outputs_grid_cpp, n_samples_per_dim_grid)
        h_cpp = ax.plot_wireframe(
            inputs_0_on_grid, inputs_1_on_grid, outputs_on_grid, rstride=1, cstride=1
        )
    else:
        raise ValueError(f"Cannot plot input data with a dimensionality of {n_dims}")

    plt.setp(h_pyt, linestyle="-", linewidth=4, color=(0.8, 0.8, 0.8))
    plt.setp(h_cpp, linestyle="--", linewidth=2, color=(0.2, 0.2, 0.8))

    plt.gcf().suptitle(basename)

    if save:
        plt.gcf().savefig(Path(directory, f"{basename}.png"))


def main(show=False, save=False):
    for fa_name in ["RBFN", "LWR"]:
        for n_dims in [1, 2]:
            train(fa_name, n_dims, save)
    if show:
        plt.show()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--show", action="store_true", help="show plots")
    parser.add_argument("--save", action="store_true", help="save plots")
    args = parser.parse_args()

    main(args.show, args.save)
