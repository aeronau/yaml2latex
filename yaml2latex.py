#!/usr/bin/python
import yaml
import os
import sys
import argparse
import subprocess
from datetime import datetime
import importlib
import itertools
import re

"""Random value to avoid printing the whole substituting str if
it is longer than limit_print.
"""
limit_print = 15

"""Left word identifies the field (template, dependencies, selectors).
The right word is the key or word that has to be used in the YAML file.
If the value for of the key "selectors" (the word to its right) is changed to
"options", then the YAML file should have an "options" field instead of
"selectors".
"""
yaml_fields = {
    "template": "template",  # Template field
    "dependencies": "dependencies",  # Dependencies field
    "selectors": "select",  # List of selectors
    "replace": "replace",  # Replace list
    "vars": "vars",  # Variables
    "system": "texconverter"  # Compile TeX file (i.e. pdflatex, xelatex,...)
}


"""Left word identifies the type of the element. The right word is the key
or word that has to be used in the YAML file to trigger the special
treatment of the element (parse environment or command instead of a simple
list or dict).
"""
yaml_reserved = {
    "file": "file",
    "var": "var",
    "env": "env",
    "opts": "opts",
    "args": "args",
    "tablerow": "tablerow",
    "tag": ("<<<< ", " >>>>"),
}


def list2args(args_list, delimiters=("{", "}"), **kwargs):
    """Convert a list [elem1, elem2, elem3, ...] to a string
    '{elem1}{elem2}{elem3}'.
    Delimiters can be changed.
    Promotion of selector dictionaries is carried out.
    kwargs are passed down to parseElem(...)
    """

    args = []
    for arg in args_list:  # Make each element a one-elem list
        get_promotion = promoteSelection(arg, **kwargs)
        if get_promotion is not None:
            args += get_promotion
        else:
            args.append(parseElem(arg, **kwargs))

    str_args = ""
    if args and args_list != [None]:  # Not empty and is not the list [None]
        for arg in args:
            str_args += delimiters[0] + arg + delimiters[1]

    return str_args


def promoteSelection(elem, select_dict, **kwargs):
    """
    If elem is a dict {selector: {opt1: ..., opt2: ...}} the option opt
    specified by the selector (in select_dict) is promoted. If the diict
    has a key in select_dict.keys(), then what is returned is the value of the
    dictionary elem that has the key opt specified in selec_dict. This is always
    a list (the one specified in opt) or a single member list (if it contains
    a str).
    """

    full_kwargs = {**{"select_dict": select_dict}, **kwargs}  # Rebuild kwargs by merging dicts

    if isinstance(elem, dict) and select_dict:
        for selector in select_dict.keys():
            if selector in elem.keys():
                elems_pre = elem[selector][select_dict[selector]]  # Nested selectors
                elems_pre = elems_pre if isinstance(elems_pre, list) else [elems_pre]

                elems = []
                for elem in elems_pre:
                    elems.append(parseElem(elem, **full_kwargs))
                return elems

    return None  # Return None if no promotion


def parseStr(str_in, replace_dict=None, **kwargs):
    """If string contains a str ''<<<< tag >>>>' look in the replace_dict for
    the substitution.
    """

    full_kwargs = {**{"replace_dict": replace_dict}, **kwargs}  # Rebuild kwargs by merging dicts

    if replace_dict:
        for t in re.findall(yaml_reserved["tag"][0]+'(.+?)'+yaml_reserved["tag"][1], str_in):  # <<<< tag >>>>
            str_in = replaceTag(str_in, t, replace_dict[t], parse=True, **full_kwargs)

    return str(str_in)


def parseElem(elem, **kwargs):
    """If elem is a dict, the key is a tag and the value is what is to be
    converted to a string. Parse each of the entries and append them in a str.
    If elem is a list, iterate over each element and parse it again. Append to
    a single str.
    If it is not an iterable, then convert to str..
    """

    if isinstance(elem, dict):

        the_str = ""
        for k, v in elem.items():
            the_str += parseEntry(k, v, **kwargs)

        return the_str

    elif isinstance(elem, list):

        the_str = ""
        for e in elem:
            the_str += parseElem(e, **kwargs) + " "

        return the_str

    else:
        # Convert to string as it is an element that does not have children
        return parseEntry(elem, **kwargs)


# Combinations: key-value, str-None, str-list, str-dict...
def parseEntry(subelem1, subelem2=None, select_dict=None, replace_dict=None, vars_dict=None, yaml_dir="."):
    """Convert to str according to the types and contents of subelem1 and
    subelem2. If subelem1 is a reserved word, perform a specific action.
    In general, if subelem2 is a list or a dict, then subelem1 is the name
    of the LaTeX command. subelem2 contains the arguments (if list) or
    options and arguments (if dict with keys opts and args, respectively).If the
    dict does not have the specified keys, then parse the subelem2 dict values.
    If is not any of the cases above, convert subelem2 to string.
    """

    all_dicts = {  # Keys should have the name of the parameters in parseEntry
        "select_dict": select_dict,
        "replace_dict": replace_dict,
        "vars_dict": vars_dict,
        "yaml_dir": yaml_dir
    }  # This dictionary is created to easen recursion without creating global variables

    # subelem1 is the key of the dict {selector1: 'english', selector2: 1.225, ...}
    if select_dict and subelem1 in select_dict.keys():
        """Select value with the key that is specified in the selector
        select_dict[subelem1].
        """
        return parseElem(subelem2[select_dict[subelem1]], **all_dicts)

    elif subelem1 == yaml_reserved["file"]:  # subelem1 is a file
        """Replace with file. If the file is a YAML file, then process it.
        Otherwise, assume that the file is already a LaTeX file.
        """
        include_file = os.path.join(yaml_dir, subelem2)
        include_pre, include_ext = os.path.splitext(include_file)

        if include_ext == ".yaml":
            include_dict = yaml2dict(include_file)
            include_str = parseElem(include_dict, **all_dicts)
            return include_str
        else:
            with open(include_file, 'r') as fin:
                subst_file = fin.read()
                return subst_file

    elif subelem1 == yaml_reserved["var"]:  # subelem1 is a variable
        """Choose variable from vars_dict.
        """
        # Choose variable in vars with name specified in subelem2
        return parseElem(vars_dict[subelem2], **all_dicts)

    elif subelem1 == yaml_reserved['env']:  # subelem1 refers to a LaTeX environment
        """Create LaTeX environment with contents specified in subelem2.
        """

        name = str(subelem2["name"])

        str_opts = ""
        if yaml_reserved["opts"] in subelem2.keys():
            str_opts = list2args(subelem2[yaml_reserved["opts"]], ("[", "]"), **all_dicts)

        str_args = ""
        if yaml_reserved["args"] in subelem2.keys():
            str_args = list2args(subelem2[yaml_reserved["args"]], **all_dicts)

        return "\n" + \
            "\\begin{" + name + "}" + str_opts + str_args + "\n" + \
            list2args(subelem2["contents"], ("", "\n"), **all_dicts) + \
            "\\end{" + name + "}" + \
            "\n"  # the contents key must exist, otherwise the environment does not make sense

    elif subelem1 == yaml_reserved["tablerow"]:
        """List subelem2 with [elem1, elem2, ...] is returned as the str
        'elem1 & elem2 & ...'.
        """

        args = []
        for arg in subelem2:  # Its children are the arguments
            args.append(parseElem(arg, **all_dicts))
        str_args = ""
        for i, arg in enumerate(args):
            if i != len(args)-1:
                str_args += arg + " & "
        str_args += args[i]

        return str_args + "\\\\" + "\n"

    elif isinstance(subelem2, list):  # subelem1 is the name of the command, and the list subelem2 contains the arguments
        """Create the latex command \subelem1{s1}{s2}{...}, where s1, s2, ...
        are the elements of the list subelem2.
        """

        return "\\" + str(subelem1) + list2args(subelem2, **all_dicts) + "\n"

    elif isinstance(subelem2, dict):
        """Create the latex command \subelem1[o1][o2][...]{s1}{s2}{...},
        where o1, o2, ... and s1, s2, ... are the elements listed in the keys
        opts and args of subelem2.
        Parse again subelem2 if it does not contain the keys.
        """

        # subelem1 is the name of the command, and the dict subelem2 contains the arguments args and options opts
        if yaml_reserved["args"] in subelem2.keys():
            str_opts = ""
            if yaml_reserved["opts"] in subelem2.keys():
                str_opts = list2args(subelem2[yaml_reserved["opts"]], ("[", "]"), **all_dicts)

            str_args = list2args(subelem2[yaml_reserved["args"]], **all_dicts)

            # Its children are the arguments
            return "\\" + str(subelem1) + str_opts + str_args + "\n"
        else:  # Parse the new dictionary

            # print("HELP: This dictionary might not make any sense", subelem2)
            return parseElem(subelem2, **all_dicts)

    else:  # It is a single element that can be written down
        """Return the str, it does not need to be parsed again. End of
        recursion.
        """
        return parseStr(str(subelem1), **all_dicts)  # Convert to string


def replaceTag(string, tag, subst, parse=True, **kwargs):

    rtag = yaml_reserved["tag"][0]+tag+yaml_reserved["tag"][1]  # <<<< tag >>>>

    if parse:
        subst = parseElem(subst, **kwargs)

    print("Substituting:", rtag, "→",
          subst[:limit_print]+"..." if len(subst) > limit_print else subst)

    return string.replace(rtag, subst)


def replaceAllTags(tex_template, replace_dict, select_dict=None, vars_dict=None, yaml_dir="."):
    """Replaces <<<< tag >>>> with the specified value in replace_dict that has
    the key tag.
    """

    with open(tex_template, 'r') as fin:
        template = fin.read()

    for tag, subst in replace_dict.items():  # Replace tag with subst (substitute)

        template = replaceTag(template, tag, subst, select_dict=select_dict,
                              replace_dict=replace_dict, vars_dict=vars_dict, yaml_dir=yaml_dir)

    for tag, subst in select_dict.items():

        template = replaceTag(template, tag, subst, parse=False, select_dict=select_dict,
                              replace_dict=replace_dict, vars_dict=vars_dict, yaml_dir=yaml_dir)

    return template


def yaml2dict(yaml_in):
    """Reads YAML file and returns the corresponding dict.
    """

    with open(yaml_in, 'r') as fyaml:
        try:
            yaml_dict = yaml.safe_load(fyaml)
            print("YAML file read")
        except yaml.YAMLError as exc:
            print(exc)
    return yaml_dict


def latex2pdf(tex_in, run_dir=os.getcwd(), system="xelatex"):
    """Runs xelatex on tex_in and returns the pdf file and the log file log_out.
    """

    pre, ext = os.path.splitext(os.path.basename(tex_in))
    log_out = os.path.join(run_dir, pre+"_yaml2latex.log")
    subprocess.run([system, pre], cwd=run_dir, stdout=open(log_out, 'wb'))

    return os.path.join(run_dir, pre+".pdf"), log_out


def main():
    """Reads command line arguments and returns a latex converted-to-pdf file.
    """

    wd = os.getcwd()

    parser = argparse.ArgumentParser()
    parser.add_argument('--no-pdf', dest='pdf', action='store_false')
    # This below the other means that if no --pdf is passed, the default is True
    parser.add_argument('--pdf', dest='pdf', action='store_true')
    parser.add_argument("--"+yaml_fields["selectors"], nargs=2, action="append",
                        help="choose selector from "+yaml_fields["selectors"]+" and its value. Multiple can be specified: "+"--"+yaml_fields["selectors"]+" SELECTOR VALUE "+"--"+yaml_fields["selectors"]+" SELECTOR VALUE ..."+"IMPORTANT: the flag takes the name of the key in the YAML file")
    parser.add_argument("--"+yaml_fields["template"], help="override " +
                        yaml_fields["template"]+" with the file specified")
    # Default source is "classes/cv/cv.yaml"
    parser.add_argument("--"+yaml_fields["system"], default="xelatex")
    parser.add_argument("input", nargs='?', default="cv.yaml")
    parser.add_argument("output", nargs='?')

    args_dict = vars(parser.parse_args())

    tex_template = args_dict[yaml_fields["template"]]

    yaml_in = args_dict["input"]
    yaml_dir = os.path.dirname(os.path.abspath(yaml_in))
    yaml_filename = os.path.basename(yaml_in)
    # basename = os.path.splitext(os.path.basename(yaml_filename))[0]  # From "file.yaml" to "file"

    print("yaml_in", yaml_in, yaml_dir)

    yaml_dict = yaml2dict(yaml_in)
    try:
        tex_template = os.path.join(
            yaml_dir, yaml_dict[yaml_fields["template"]]) if tex_template is None else tex_template
    except:
        print("No template specified neither as flag nor in "+yaml_filename)

    # yaml_dict has the usual structure
    if isinstance(yaml_dict, dict) and any(x in yaml_fields.keys() for x in yaml_dict.keys()):
        dependencies = yaml_dict[yaml_fields["dependencies"]
                                 ] if yaml_fields["dependencies"] in yaml_dict.keys() else None
        # if not dependencies:
        #     dependencies = [None]
        replace_dict = yaml_dict[yaml_fields["replace"]
                                 ] if yaml_fields["replace"] in yaml_dict.keys() else None
        # if not replace_dict:
        #     replace_dict = [None]
        vars_dict = yaml_dict[yaml_fields["vars"]
                              ] if yaml_fields["vars"] in yaml_dict.keys() else None
        # if not vars_dict:
        #     vars_dict = [None]
        selectors = yaml_dict[yaml_fields["selectors"]
                              ] if yaml_fields["selectors"] in yaml_dict.keys() else None
        # if not selectors:
        #     selectors = [None]
    else:
        dependencies = replace_dict = vars_dict = selectors = None

    tex_out = args_dict["output"]

    date_today = datetime.today().strftime('%Y%m%d')

    select_list = args_dict[yaml_fields["selectors"]]
    if not select_list:
        select_list = []  # If void

    selector_dict = dict()
    for selector in select_list:
        selector_key = selector[0]
        selector_val = selector[1]

        if selector_key not in selectors:
            print("Ignoring selection "+selector_key+" unspecified in the YAML file...")
            continue

        if selector_key not in selector_dict.keys():
            selector_dict[selector_key] = {selector_val}  # Create set of element selector_val
        else:
            selector_dict[selector_key].add(selector_val)

    if isinstance(selectors, dict):  # This means that it contains defaults
        for selector_key, selector_vals in selectors.items():  # Add the selectors and its defaults specified in the
            # Ensure that it is a list, even if it contains one member (the only default option)
            selector_vals = selector_vals if isinstance(selector_vals, list) else [selector_vals]
            for selector_val in selector_vals:
                if selector_key not in selector_dict.keys():
                    # Create set of element selector_val
                    selector_dict[selector_key] = {selector_val}
                else:
                    selector_dict[selector_key].add(selector_val)
    else:
        print("No values for "+yaml_fields["selectors"] +
              " specified (neither in the YAML file nor in the execution)")

    iter_combi = []  # [lang, density, ...] selector order of iter_sets
    iter_sets = []  # values in the order specified in iter_combi [['catalan', 1.225, ...], ['english', 3.143, ...]]
    for selector_key in selector_dict.keys():
        iter_set = []
        for selector_set in selector_dict[selector_key]:
            iter_set.append(selector_set)
        iter_sets.append(iter_set)
        iter_combi.append(selector_key)

    for iter_params in itertools.product(*iter_sets):  # iterate each set in the order iter_combi

        select_dict = dict(zip(iter_combi, iter_params))

        combi_str = ""
        for i, _ in enumerate(iter_combi):
            combi_str += iter_combi[i] + "-" + iter_params[i]
            if i != len(iter_combi)-1:
                combi_str += "_"

        if tex_out is not None:
            tex_dir = os.path.dirname(os.path.abspath(tex_out))
            tex_pre, tex_ext = os.path.splitext(tex_out)
            tex_filename = tex_pre + "_"+combi_str+".tex" if combi_str else tex_pre + ".tex"
        else:
            tex_dir = os.path.abspath(os.path.join("generated", date_today))
            if combi_str:
                tex_filename = os.path.join(tex_dir, os.path.splitext(
                    yaml_filename)[0]+"_"+combi_str+"_"+date_today+".tex")
            else:
                tex_filename = os.path.join(tex_dir, os.path.splitext(
                    yaml_filename)[0]+".tex")

        if not os.path.exists(tex_dir):
            os.makedirs(tex_dir)

        print("Creating file with paramters:", iter_combi, "=", list(iter_params))

        if dependencies:
            for dep in dependencies:  # link dependencies
                if dep not in os.listdir(tex_dir):
                    target = os.path.join(yaml_dir, dep)
                    dep_basename = os.path.basename(dep)
                    linkName = os.path.join(tex_dir, dep_basename)
                    tmpLink = os.path.join(tex_dir, dep_basename+"_tmp")
                    os.symlink(target, tmpLink)
                    os.rename(tmpLink, linkName)

        if replace_dict:
            tex_replaced = replaceAllTags(tex_template, replace_dict,
                                          select_dict, vars_dict, yaml_dir)
        else:  # Parse dict directly if the YAML file does not have all the usual keys
            tex_replaced = parseElem(yaml_dict)

        with open(tex_filename, "w") as fout:
            fout.write(tex_replaced)

        file_out = tex_filename
        if args_dict["pdf"]:
            pdf_out, log_out = latex2pdf(tex_filename, run_dir=tex_dir,
                                         system=args_dict[yaml_fields["system"]])
            print("XeLaTeX messages:", log_out)
            file_out = pdf_out

        print("Output file:", file_out)
        print()


if __name__ == "__main__":
    main()
