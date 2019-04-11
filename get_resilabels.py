#!/usr/bin/env python
"""
Take .txt output of multiple structure alignment between PDBs as generated by gesamt
(http://www.ccp4.ac.uk/dist/html/gesamt.html) and output label files to use with GetContacts.
"""

import os


def parse_two_queries(gesamt_lines):
    proteins = []
    for idx, line in enumerate(gesamt_lines):
        if "reading QUERY structure" in line or "reading TARGET structure" in line or "reading FIXED structure" in line or "reading MOVING structure" in line:
            protein_filename = line.split("'")[1]
            protein, _ = os.path.splitext(protein_filename)
            proteins.append(protein)

    # get the index of the first line of the alignment and the index of the last line of the alignment
    alignment_start_idx = None
    alignment_end_idx = None
    for idx, line in enumerate(gesamt_lines):
        if not alignment_start_idx:
            line_tokens = [token.strip() for token in line.split("|")]
            # the header line looks like this: "|    Query    |  Dist.(A)  |   Target    |"
            if (
                ("Query" in line_tokens or "FIXED" in line_tokens)
                and "Dist.(A)" in line_tokens
                and ("Target" in line_tokens or "MOVING" in line_tokens)
            ):
                alignment_start_idx = idx + 2
        else:
            if "'" in line:
                alignment_end_idx = idx
                break

    # grab all lines in the file belonging to the alignment
    alignment_lines = gesamt_lines[alignment_start_idx:alignment_end_idx]

    # slice out three tokens for each line, corresponding to Query Residue, Distance, and Target Residue
    # for example: "|H- A:LEU  75 | <**0.82**> |H- A:LEU  65 |" -> ["H- A:LEU  75", "H- A:LEU  65"]
    alignment_lines = [
        [line.split("|")[idx].strip() for idx in [1, 3]] for line in alignment_lines
    ]

    # slice out the residue name for each token in each line
    # for example, the following line: ["H- A:LEU  75", "H- A:LEU  65"] -> ["A:LEU:75", "A:LEU:65"]
    alignment_lines = [
        [
            token[-9:-4] + ":" + (str(int(token[-4:])).strip())
            if len(token) > 0
            else ""
            for token in line
        ]
        for line in alignment_lines
    ]

    return alignment_lines, proteins


def parse_more_than_two_queries(gesamt_lines):
    proteins = []
    for idx, line in enumerate(gesamt_lines):
        if "... reading file" in line:
            protein_filename = line.split("'")[1]
            protein, _ = os.path.splitext(protein_filename)
            proteins.append(protein)

    alignment_start_idx = None
    alignment_end_idx = None
    for idx, line in enumerate(gesamt_lines):
        if not alignment_start_idx:
            line_tokens = [token.strip() for token in line.split("|")]
            if "Disp." in line_tokens:
                alignment_start_idx = idx + 2
        else:
            if "'" in line:
                alignment_end_idx = idx
                break

    # grab all lines in the file belonging to the alignment
    alignment_lines = gesamt_lines[alignment_start_idx:alignment_end_idx]

    reformatted_alignment_lines = []
    for line in alignment_lines:
        # first, replace any instance of the weird delimiter with the asterisk in the center: "6.034 |*|  A:CYS 341 |*|  A:MET 456 |*|  D:LEU 559" -> "6.034 | |  A:CYS 341 | |  A:MET 456 | |  D:LEU 559"
        line = line.replace("|*|", "| |")

        # next, remove the line delimeters: "6.034 | |  A:CYS 341 | |  A:MET 456 | |  D:LEU 559" -> "['6.034', 'A:CYS 341', 'A:MET 456', 'D:LEU 559']"
        line = [token.strip() for token in line.split("| |")]

        # remove the first (displacement) column from each line: "['6.034', 'A:CYS 341', 'A:MET 456', 'D:LEU 559']" -> "['A:CYS 341', 'A:MET 456', 'D:LEU 559']"
        line = line[1:]

        # some of the tokens in the line have an extra field. remove these: "H|A:ASN 103" -> "A:ASN 103"
        line = [(token.split("|")[1] if "|" in token else token) for token in line]

        # convert the residue name for each token in each line
        # for example, the following line: ["A:LEU  75", "A:LEU  65"] -> ["A:LEU:75", "A:LEU:65"]
        line = [
            token[:5] + ":" + str(int(token[5:])) if len(token) > 0 else token
            for token in line
        ]
        reformatted_alignment_lines.append(line)

    return reformatted_alignment_lines, proteins


def main(argv=None):
    # Set up command line arguments
    import argparse

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--input_gesamt",
        required=True,
        type=str,
        help="A .txt file produced by redirecting output from gesamt to a file",
    )
    parser.add_argument(
        "--output_path", required=True, type=str, help="Path to output directory"
    )
    parser.add_argument(
        "--proteins",
        required=False,
        type=str,
        nargs="+",
        help='Optionally, provide a space-delimited list of names of all proteins in the gesamt input file. Protein names should be specified in the order that the proteins were inputted to the gesamt program. For example, if you called gesamt with "gesamt foo1.pdb foo2.pdb foo3.pdb", you can specify "--proteins foo1 foo2 foo3"',
    )

    args = parser.parse_args(argv)
    input_gesamt = args.input_gesamt
    output_path = args.output_path
    input_proteins = args.proteins

    # input_gesamt = "two_queries/two_queries.txt"
    with open(input_gesamt, "r") as r_open:
        gesamt_lines = [
            line.strip() for line in r_open.readlines() if len(line.strip()) > 0
        ]

    # parse the input file differently depending on whether there are 2 queries or >2 queries
    if "reading QUERY structure" in "".join(gesamt_lines) or "reading FIXED structure" in "".join(gesamt_lines):
        alignment_lines, proteins = parse_two_queries(gesamt_lines)
    else:
        alignment_lines, proteins = parse_more_than_two_queries(gesamt_lines)
    proteins = input_proteins if input_proteins is not None else proteins

    alignment_lines = [
        {proteins[idx]: residue for idx, residue in enumerate(line)}
        for line in alignment_lines
    ]
    for line in alignment_lines:
        line["generic_resname"] = "-".join(
            [line[protein] if len(line[protein]) > 0 else "None" for protein in line]
        )

    for protein in proteins:
        # write output file
        with open("{}/{}.label".format(output_path, protein), "w+") as w_open:
            for line in alignment_lines:
                if len(line[protein]) == 0:
                    continue
                w_open.write(
                    "{}\t{}\t\n".format(line[protein], line["generic_resname"])
                )


if __name__ == "__main__":
    main()
