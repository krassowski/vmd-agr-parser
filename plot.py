#!/usr/bin/env python3
"""Simple script for plotting .agr (Grace) files created with VMD.

Visual Molecular Dynamics allows generation of .agr files which are no longer
properly interpreted by xmgrace software. This small tool allows to quickly
plot data from an agr file (using matplotlib underneath) or to export the data
to other formats such as csv, svg or png.
"""
import argparse
from collections import OrderedDict
from collections import namedtuple
import csv
from os.path import basename
from shlex import split


SUPPORTED_FORMATS = ['csv', 'svg', 'png', 'jpg']


Vector = namedtuple('Vector', ('x', 'y'))


class Layer:
    """Layer represents a single variable in agr file, with its:
        - name (extracted from legend line)
        - data (so all points from corresponding ampersand-limited section)
    """
    def __init__(self, name):
        self.name = name
        self.data = OrderedDict()

    @property
    def keys(self):
        return list(self.data.keys())

    @property
    def values(self):
        return list(self.data.values())


class VmdAgrPlot:
    """VmdAgrPlot corresponds to a single agr file, which should be provided
    on initialization. Allows to create plots and export to csv format.
    """

    def __init__(self, path, restrict_to=None):
        self.title = ''
        self.layers = []
        self.restrict_to = restrict_to
        self.load(path)

    @property
    def chosen_layers(self):
        return [
            layer
            for layer in self.layers
            if (
                not self.restrict_to or
                layer.name in self.restrict_to
            )
        ]

    def parse_plot_configs(self, agr_file):

        position = 0

        for line in agr_file:

            if line.startswith('@'):
                # keep track on position in file
                position += len(line)
            else:
                # if we hit the end of config section escape the loop
                break

            line = line.strip()

            command, *values = split(line)
            command = command.lstrip('@')

            if command == 'title':
                title = values[0]
                self.title = title
            elif command.startswith('s') and values[0] == 'legend':
                layer_name = values[1]
                self.layers.append(Layer(layer_name))
            elif command == 'type':
                assert values[0] == 'xy'
            else:
                print('Unrecognized command: %s' % command)

        # go to previous position (one line back) and finish the work
        agr_file.seek(position)

    def parse_coordinates(self, agr_file):

        for layer in self.chosen_layers:

            for line in agr_file:
                line = line.strip()

                if line == '&':
                    break

                x, y = [float(c) for c in line.split()]

                if x in layer.data:
                    print(
                        'Data inconsistency: %s occurs twice as x'
                        % x
                    )
                layer.data[x] = y

    def load(self, agr_file):
        """Parses given file using helper functions.

        There are following assumptions about file structure:
            - all configuration lines (@) are placed on top
            - after each data section there is a terminal ampersand (&)
        """
        self.parse_plot_configs(agr_file)
        self.parse_coordinates(agr_file)

    def to_csv(self, path):
        """Saves plot data into a csv file under given path.

        Each variable/layer will be represented by two columns in output file:
        'variable.x' and 'variable.y'. Such representation makes sense because
        .agr files created with VMD commonly represent how different variables
        were changing during simulation; then x-points represent subsequent
        simulation frames and are consistent between different variables."""

        headers = [
            '%s.%s' % (layer.name, coord)
            for layer in self.chosen_layers
            for coord in ('x', 'y')
        ]

        with open(path, 'w', newline='') as csv_file:
            writer = csv.DictWriter(csv_file, headers)
            writer.writeheader()

            for layer in self.chosen_layers:
                name = layer.name

                for x, y in layer.data.items():
                    writer.writerow({
                        name + '.x': x,
                        name + '.y': y
                    })

    def plot(
            self, scale=Vector(1, 1), axes_labels=None,
            legend_pos=None, labels=None
    ):
        """Creates a matplotlib plot with given parameters.

        Returns:
            matplotlib pyplot if successfuly generated,
            False if plot generation failed.
        """

        try:
            import matplotlib.pyplot as plt
        except ImportError:
            print(
                'Matplotlib not found. Matplotlib is required for plotting. '
                'Use --do_not_plot to run this tool without plot generation. '
                'Note that without plotting only export to csv is possible.'
            )
            return False

        if labels:
            if len(labels) != len(self.chosen_layers):
                print(
                    'There should be exactly as many labels '
                    'given as there are variables chosen.'
                )
                return False

        for i, layer in enumerate(self.chosen_layers):
            plt.plot(
                [scale.x * x for x in layer.keys],
                [scale.y * y for y in layer.values],
                label=(
                    labels[i]
                    if labels
                    else layer.name
                )
            )

        plt.title(self.title)

        if axes_labels:
            plt.xlabel(axes_labels.x)
            plt.ylabel(axes_labels.y)

        if legend_pos:
            plt.legend(bbox_to_anchor=legend_pos)

        return plt


def create_argument_parser():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        'input_file',
        type=argparse.FileType('r'),
        help='Path to .agr file'
    )
    parser.add_argument(
        '--do_not_plot',
        action='store_true',
        help='Skip plot generation (useful if matplotlib is not available)'
    )
    parser.add_argument(
        '-t', '--title',
        default=None,
        type=str,
        help='If not specified it title from file will be used'
    )
    parser.add_argument(
        '-x', '--axis_x',
        default='frame',
        help='What text to show below x axis'
    )
    parser.add_argument(
        '-y', '--axis_y',
        default='y',
        help='What text to show beside y axis'
    )
    parser.add_argument(
        '-r', '--restrict_to',
        default=None,
        type=str,
        nargs='+',
        help='Specify which variables should be plotted'
    )
    parser.add_argument(
        '-e', '--export',
        type=str,
        default=None,
        choices=SUPPORTED_FORMATS,
        help='Export plot to specified file format.'
    )
    parser.add_argument(
        '-s', '--scale',
        default=(1, 1),
        type=float,
        nargs=2,
        help='Scale of the plot (two floats: x, y)'
    )
    parser.add_argument(
        '-l', '--legend_position',
        default=(1, 1),
        type=float,
        nargs=2,
        help='Position of the legend (two floats: x, y)'
    )
    parser.add_argument(
        '--labels',
        default=None,
        type=str,
        nargs='+',
        help='Text to use on labels instead of variable names'
    )

    return parser


def main():
    arg_parser = create_argument_parser()

    args = arg_parser.parse_args()

    agr_plot = VmdAgrPlot(
        args.input_file,
        restrict_to=args.restrict_to
    )

    # override title if given
    if args.title:
        agr_plot.title = args.title

    if not args.do_not_plot or args.export:
        plot = agr_plot.plot(
            scale=Vector(*args.scale),
            legend_pos=Vector(*args.legend_position),
            axes_labels=Vector(args.axis_x, args.axis_y),
            labels=args.labels
        )
        if not plot:
            print('Plot generation failed')
            return

    if args.export:
        filename = basename(args.input_file.name)
        export_filename = '%s.%s' % (filename, args.export)

        if args.export == 'csv':
            agr_plot.to_csv(export_filename)
        else:
            plot.savefig(export_filename)

        layers_count = len(agr_plot.chosen_layers)
        print(
            'Exported %s layer(s) to %s.' %
            (layers_count, export_filename)
        )

    if not args.do_not_plot:
        plot.show()


if __name__ == '__main__':
    main()
