import configparser
import argparse
import csv
import os

pattern_igzo = {
    '12': '1',
    '13': '3',
    '14': '2',
    '1': '5',
    '2': '4',
    '3': '6',
    '0': '0'
}

pattern_e6 = {
    '2': '1',
    '5': '2',
    '6': '3',
    '8': '4',
    '10': '5',
    '12': '6',
    '0': '0'
}

pattern_pmv = {
    '1': '6',
    '2': '1',
    '0': '0'
}

def process_table(fn, newfn, pattern):
    table = {}
    with open(fn, newline='') as csvfile:
        csvreader = csv.reader(csvfile, delimiter=',')
        for row in csvreader:
            src = row[0]
            dst = row[1]
            seq = row[2:]
            newseq = []
            for phase in seq:
                newseq += pattern[phase]
            table[f'{src}_{dst}'] = newseq
    with open(newfn, 'w') as csvfile: 
        for src in range(16):
            for dst in range(16):
                try:
                    ss = ','.join(table[f'{src}_{dst}'])
                    csvfile.write(f'{src},{dst},{ss}\n')
                except KeyError:
                    continue

def main():
    parser = argparse.ArgumentParser(prog='wvfm_converter')
    parser.add_argument('filename')
    parser.add_argument('-p', '--pattern', required=True, choices=['igzo', 'e6', 'pmv'])

    args = parser.parse_args()
    pattern = {}
    if args.pattern == 'igzo':
        pattern = pattern_igzo
    elif args.pattern == 'e6':
        pattern = pattern_e6
    elif args.pattern == 'pmv':
        pattern = pattern_pmv

    config = configparser.ConfigParser()
    config.read(args.filename)
    #print(config.sections())

    version = config['WAVEFORM']['VERSION']
    if (version != '2.0') and (version != '2.1'):
        raise Exception("Unsupported")
    prefix = config['WAVEFORM']['PREFIX']
    # name = config['WAVEFORM']['NAME']
    bpp = int(config['WAVEFORM']['BPP'])
    modes = int(config['WAVEFORM']['MODES'])
    temps = int(config['WAVEFORM']['TEMPS'])
    tables = int(config['WAVEFORM']['TABLES'])
    #outbpp = int(config['WAVEFORM']['OUTBPP']) if version == '2.1' else 2
    outbpp = 4
    unidir = int(config['WAVEFORM']['UNIDIR']) if version == '2.1' else 0

    # This tool always output in V2.1 to support OUTBPP = 4
    version = '2.1'

    # Get all framecounts
    # fc = []
    # for i in range(tables):
    #     fc.append(config['WAVEFORM'][f'TB{i}FC'])

    # trange = []
    # for i in range(temps):
    #     trange.append(config['WAVEFORM'][f'T{i}RANGE'])

    dirname = os.path.dirname(os.path.abspath(args.filename))
    suffix = args.pattern

    for i in range(tables):
        oldname = f'{prefix}_TB{i}.csv'
        newname = f'{prefix}_{suffix}_TB{i}.csv'
        process_table(os.path.join(dirname, oldname),
                      os.path.join(dirname, newname), pattern)

    with open(os.path.join(dirname, f'{prefix}_{suffix}_desc.iwf'), 'w') as fp:
        fp.write('[WAVEFORM]\n')
        fp.write(f'VERSION = {version}\n')
        fp.write(f'PREFIX = {prefix}_{suffix}\n')
        fp.write(f'NAME = {config['WAVEFORM']['NAME']}\n')
        fp.write(f'BPP = 4\n')
        fp.write(f'MODES = {modes}\n')
        fp.write(f'TEMPS = {temps}\n')
        fp.write(f'TABLES = {tables}\n')
        if version == '2.1':
            fp.write(f'OUTBPP = {outbpp}\n')
            fp.write(f'UNIDIR = {unidir}\n')
        fp.write('\n')
        for i in range(temps):
            fp.write(f'T{i}RANGE = {config['WAVEFORM'][f'T{i}RANGE']}\n')
        fp.write('\n')
        for i in range(tables):
            fp.write(f'TB{i}FC = {config['WAVEFORM'][f'TB{i}FC']}\n')
        fp.write('\n')
        for i in range(modes):
            fp.write(f'[MODE{i}]\n')
            fp.write(f'NAME = {config[f'MODE{i}']['NAME']}\n')
            for j in range(temps):
                fp.write(f'T{j}TABLE = {config[f'MODE{i}'][f'T{j}TABLE']}\n')
            fp.write('\n')

if __name__ == "__main__":
    main()