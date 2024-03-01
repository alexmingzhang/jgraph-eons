import argparse
import json
import numpy
import subprocess
import sys
import typing

parser = argparse.ArgumentParser(
                    prog=sys.argv[0],
                    description="Creates a postscript graph from the EONS standard output")

parser.add_argument("filename",
    help="EONS standard output file")
parser.add_argument("-j", "--jgraph",
    default="./jgraph",
    help="jgraph executable path",
    type=str)
parser.add_argument("-xs", "--xsize",
    default=6,
    help="size of x axis",
    type=float)
parser.add_argument("-ys", "--ysize",
    default=6,
    help="size of y axis",
    type=float)
parser.add_argument("-min", "--graph_min",
    action="store_true",
    help="Graph the minimum fitness of each epoch")
parser.add_argument("-sc", "--graph_scatter",
    action="store_true",
    help="Graph a scatter plot of all fitnesses")
parser.add_argument("-bo", "--graph_box_and_whiskers",
    action="store_true",
    help="Graph a box of whisker plot of fitnesses of each epoch")
parser.add_argument("-lq", "--graph_lq",
    action="store_true",
    help="Graph the lower quartile fitness of each epoch")
parser.add_argument("-med", "--graph_med",
    action="store_true",
    help="Graph the median fitness of each epoch")
parser.add_argument("-uq", "--graph_uq",
    action="store_true",
    help="Graph the upper quartile fitness of each epoch")
parser.add_argument("-max", "--graph_max", 
    action="store_true",
    help="Graph the maximum fitness of each epoch")
parser.add_argument("-avg", "--graph_average", 
    action="store_true",
    help="Graph the average fitness of each epoch")

# Color palette from https://davidmathlogic.com/colorblind/#%23000000-%23E69F00-%2356B4E9-%23009E73-%23F0E442-%230072B2-%23D55E00-%23CC79A
color_palette = (
    (51, 34, 136),
    (17, 119, 51),
    (68, 170, 153),
    (136, 204, 238),
    (221, 204, 119),
    (204, 102, 119),
    (170, 68, 153),
    (136, 34, 85))
color_palette_i = 0

marktypes = ("box", "circle", "diamond", "triangle", "x", "cross", "ellipse")
marktype_i = 0

def cycle_color() -> tuple[int, int, int]:
    global color_palette
    global color_palette_i
    color = color_palette[color_palette_i]
    color_palette_i = (color_palette_i + 1) % len(color_palette)
    return color

def cycle_marktype() -> str:
    global marktypes
    global marktype_i
    marktype = marktypes[marktype_i]
    marktype_i = (marktype_i + 1) % len(marktypes)
    return marktype

# Generates the jgraph stdin to graph data
def jgraph_line(data: [int], label: str, linetype = "dashed", marktype = "circle", color = (0, 0, 0), fillcolor = (255, 255, 255)) -> str:
    jgraph_stdin = "newline marktype {marktype} linetype {linetype} color {r} {g} {b} cfill {fr} {fg} {fb} pts\n".format(
        marktype = marktype,
        linetype = linetype,
        r = color[0] / 255,
        g = color[1] / 255,
        b = color[2] / 255,
        fr = fillcolor[0] / 255,
        fg = fillcolor[1] / 255,
        fb = fillcolor[2] / 255)

    for x, y in enumerate(data):
        jgraph_stdin += "{} {}\n".format(x, y)

    jgraph_stdin += "label : {}\n".format(label)
    return jgraph_stdin

args = parser.parse_args()
# Read EONS stdout file
epoch: int = 0
max_fitness: int = 0
best_fitnesses: [int] = []
all_fitnesses: [[int]] = []
quantiles: [[int]] = []
averages: [int] = []

minimums: [int] = []
lower_quartiles: [int] = []
medians: [int] = []
upper_quartiles: [int] = []
maximums: [int] = []

with open(args.filename) as eons_stdout:
    for line in eons_stdout:
        line_words = line.split()

        if line_words[0] == "Epoch:":
            epoch = int(line_words[1])
            best_fitness = int(line_words[5])
            best_fitnesses.append(best_fitness)
            if best_fitness > max_fitness:
                max_fitness = best_fitness

        elif line[0] == "{":
            all_fitnesses.append([])
            json_data = json.loads(line)
            for network in json_data["network_info"]:
                all_fitnesses[epoch].append(network["metadata"]["fitness"])

            quantile = numpy.quantile(all_fitnesses[epoch], [0, 0.25, 0.5, 0.75, 1])
            quantiles.append(quantile)
            minimums.append(quantile[0])
            lower_quartiles.append(quantile[1])
            medians.append(quantile[2])
            upper_quartiles.append(quantile[3])
            maximums.append(quantile[4])
            averages.append(numpy.average(all_fitnesses[epoch]))

jgraph_stdin = """newgraph
xaxis
    size {xsize}
    label : Epoch

yaxis
    size {ysize}
    label : Fitness
""".format(
    xsize = args.xsize,
    ysize = args.ysize)

# Box and whisker plots
br, bg, bb = cycle_color()
if args.graph_box_and_whiskers:
    for i, quantile in enumerate(quantiles):
        w = 0.4
        mx = i
        lx = mx - w / 2
        rx = mx + w / 2

        mi = quantile[0]
        lq = quantile[1]
        me = quantile[2]
        uq = quantile[3]
        ma = quantile[4]

        # Box
        jgraph_stdin += "newline poly pcfill {} {} {} color 0 0 0 pts ".format(br / 255, bg / 255, bb / 255)
        jgraph_stdin += "{} {} {} {} {} {} {} {}\n".format(lx, lq, rx, lq, rx, uq, lx, uq)

        # Upper quartile whisker
        jgraph_stdin += "newline marktype none linetype solid color 0 0 0 pts "
        jgraph_stdin += "{} {} {} {}\n".format(mx, uq, mx, ma)
        jgraph_stdin += "newline marktype none linetype solid color 0 0 0 pts "
        jgraph_stdin += "{} {} {} {}\n".format(lx, ma, rx, ma)

        # Lower quartile whisker
        jgraph_stdin += "newline marktype none linetype solid color 0 0 0 pts "
        jgraph_stdin += "{} {} {} {}\n".format(mx, lq, mx, mi)
        jgraph_stdin += "newline marktype none linetype solid color 0 0 0 pts "
        jgraph_stdin += "{} {} {} {}\n".format(lx, mi, rx, mi)

if args.graph_scatter:
    jgraph_stdin += """newcurve
    marktype circle
    fill 1
    linetype none
    pts
    """

    for i, population in enumerate(all_fitnesses):
        for fitness in population:
            jgraph_stdin += "    {} {}\n".format(i, fitness)

if args.graph_max:
    jgraph_stdin += jgraph_line(
        maximums,
        "Best",
        marktype=cycle_marktype(),
        color=cycle_color())

if args.graph_uq:
    jgraph_stdin += jgraph_line(
        upper_quartiles,
        "Upper Quartile",
        marktype=cycle_marktype(),
        color=cycle_color())

if args.graph_med:
    jgraph_stdin += jgraph_line(
        medians,
        "Median",
        marktype=cycle_marktype(),
        color=cycle_color())

if args.graph_lq:
    jgraph_stdin += jgraph_line(
        lower_quartiles,
        "Lower Quartile",
        marktype=cycle_marktype(),
        color=cycle_color())

if args.graph_min:
    jgraph_stdin += jgraph_line(
        minimums,
        "Worst",
        marktype=cycle_marktype(),
        color=cycle_color())

if args.graph_average:
    jgraph_stdin += jgraph_line(
        averages,
        "Average",
        marktype=cycle_marktype(),
        color=cycle_color())

# Run jgraph
with subprocess.Popen([args.jgraph, "-P"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as jgraph_process:
    jgraph_stdout, jgraph_stderr = jgraph_process.communicate(input=str.encode(jgraph_stdin))
    print(jgraph_stdout.decode())
