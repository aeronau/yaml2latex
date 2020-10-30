# yaml2latex

This is a script that converts a YAML file to LaTeX or PDF, as part of a one day project. The main idea was to create a script that replaced tags `<<<< tag >>>>` in a LaTeX template specified in the yaml file. However, the code is quite generic and may be used to create any LaTeX file without the need of a template. The parser has the following features:

- Create a LaTeX file from a single YAML file or replace tags in a template (intended use)
- Replace a tag with an external file
- Define custom variables to avoid copying multiple times the same thing (e.g. if `<<<< author >>>>` or `{var: description}` is found it will be replaced with the associated value in `{replace: {author: 'Arnau Prat Gasull'}}`)
- Choose text from a dictionary according to a command line argument (e.g. select a language from `{'lang': {'catalan': ..., 'english': ...}}`)

The following YAML creates a LaTeX document with `Hola món` written in it:

```
- documentclass:
    - article
- env:
    name: 'document'
    args: [~] # Same as a sublist with the single item: - ~
    contents:
      - 'Hola món'
```

A priori, a list of strings `['elem1', 'elem2', ...]` in the YAML file becomes a concatenated string in the LaTeX file `'elem1elem2...'`.

## Syntax

A LaTeX command is a dictionary key (e.g. `documentclass`) with a list `command: ['arg1', 'arg2', ...]`:

```
command:
  - 'arg1'
  - 'arg2'
  - ...
```

Because each of the elements are the arguments, the first command above becomes `\documentclass{article}`. If one needs to pass options to the command, then a list must be associated with the key `opts` and the list of arguments in the key `args`. The command `\command[opt1, opt2][opt3]{arg1}{arg2}` is created with:

```
command:
  opts:
    - 'opt1, opt2'
    - 'opt3'
  args:
    - 'arg1'
    - 'arg2'
```

If the command `\command` does not require neither options nor arguments, then a list with the single item `~` can be used `command: [~]`. To trigger the parsing as a command, a list must always be nested.

Note that an inline list can be created with `[elem1, elem2, elem3, ...]` and is as valid as the traditional dashed list. Inline dictionaries are created with `{'key1': 'val1', 'key2': 'val2', 'key3': 'val3', ...}` and are as valid as nesting keys and their values.

```
# Identical
- 'list': ['elem1', 'elem2']
- 'list':
    - 'elem1'
    - 'elem2'
# Identical
- 'dict': {'key1': 'val1', 'key2': 'val2'}
- 'dict':
    'key1': 'val1'
    'key2': 'val2'
```

## Create a LaTeX file from a YAML file

Running `./yaml2latex.py examples/slightly_complex/slightly_complex.yaml examples/slightly_complex/slightly_complex.pdf` creates the files `slightly_complex.pdf` and `slightly_complex.tex`. A log file named `slightly_complex_yaml2latex.log` is also created. If an invalid `.tex` file is created, the script will hang. In this case, it is a good idea to terminate the script and explore the `.tex` file for errors. The `slightly_complex.yaml` file is similar to the following:

```
- documentclass:
    - 'article'
- usepackage: ['supertabular']
- usepackage:
    opts:
      - 'hidelinks'
    args:
      - 'hyperref'
- usepackage:
    opts:
      - 'usenames, svgnames'
    args: ['xcolor']
- definecolor:
    - 'shade'
    - 'HTML'
    - 'F5DD9D'
- env:
    name: 'document'
    args: [~] # Same as a sublist with the single item: - ~
    contents:
      - section: ['Hola']
      - section:
          - 'A reveure'
      - colorbox:
          - 'shade'
          - env:
              name: 'supertabular'
              args: ['p{0.5\linewidth}|p{0.5\linewidth}']
              contents:
                - tablerow: # As many tablerows as specified in args
                    - 'Sóc 1,1'
                    - 'Sóc 1,2'
                - tablerow:
                    - 'Sóc 2,1'
                    - href:
                        args:
                          - 'https://www.ctan.org/'
                          - 'Sóc 2,2'
```

## Replace strings in a LaTeX template

`yaml2latex` tool is normally used to replace tags in a template file. Assuming `helloworld_template.tex` is a file located in the same directory as the YAML file, then the following replaces the tag `<<<< helloworld >>>>` in the TeX file with the string `'Hola món'`.

```
template: 'helloworld_template.tex'
replace:
  helloworld: 'Hola món'
```

The character `'` is obtained in LaTeX with `''`. Therefore, to obtain *d'hora* in the final PDF file, one should write `d''hora`.

### Replace files

Tags can also be replaced by files. They can be YAML or LaTeX files. With the dictionary below, the tag `<<<< common_preamble >>>>` is replaced with the contents of `../common/preamble.tex`, while `<<<< work_experience >>>>` is replaced with the parsed `files/work_experience.yaml`.

```
replace:
  common_preamble: {file: '../common/preamble.tex'}
  work_experience: {file: 'files/work_experience.yaml'}
```

Do not end path with `'/'`, it should be `'../common/fonts'` instead of `'../common/fonts/'`.

### Use variables

There are two ways to define the variables. In strings one may use the tag syntax `<<<< tag >>>>`. The parser will look for the key `tag` in the `replace` section and substitute it with the assigned value. Variables can also be added as dictionaries inside `vars` top-level key in the YAML file, and these may contain LaTeX commands. Variables may be nested, but always have to be defined as keys under `vars`.
```
  template: '../helloworld/helloworld_template.tex'
  replace:
    holamon: 'Hola món'
    helloworld: '<<<< helloworld >>>>'
```

Which produces the same as:

```
template: '../helloworld/helloworld_template.tex'
replace:
  helloworld: {var: myvar}
vars:
  myvar: {var: myvar2}
  myvar2: 'Hola món <<<< helloworld >>>>'
```

Obviously the following leads to a recursion error, just like having a variable refer to itself `replaceme: '<<<< replaceme >>>>'`:

```
template: '../helloworld/helloworld_template.tex'
replace:
  helloworld: {var: myvar}
vars:
  myvar: {var: myvar2}
  myvar2: 'Hola món <<<< helloworld >>>>'
```

### Choose text from multiple options

The idea is to be able to choose a string from a set of options from the command line. This is great for having multiple versions of the final document stored in the same file. This was the original idea for the project, to have a CV as a YAML file and produce a PDF file in the desired language.

```
template: '../helloworld/helloworld_template.tex'
select: ['lang']
replace:
  helloworld:
    lang:
      catalan: 'Hola món'
      english: 'Hello world'
      spanish: '...'
      french: '...'
```

The selection can be carried out using the command `./yaml2latex.py examples/simple_selector/simple_selector.yaml --select lang catalan`. Multiple `select` can be chained, producing a separate document for each language. The name of the file includes the parameters chosen. If multiple selectors are listed in `select`, then all the combinations will be produced as different documents (e.g. `--select lang catalan --select lang english --select weather rain --select weather sun` will produce 4 documents, all the possible combinations). One can also add which option is the default one (so it is always created even if not passed as an argument in the command line) as shown below (if only `--select lang french` is passed for the YAML file below, three files will be generated, one for `catalan`, one for `english` and one for `french`). Three files (every combination of the defaults) are created with `./yaml2latex.py examples/simple_selector/simple_selector.yaml`.

```
template: 'simple_selector_template.tex'
select: {'lang': ['catalan', 'english'], 'weather': ['sun']}
replace:
  helloworld:
    lang:
      catalan: 'Hola món'
      english: 'Hello world'
  temperature:
    weather:
      sun: '40C'
      rain: '20C'
  todaysweather:
    weather:
      sun:
        lang:
          catalan: 'Fa sol'
          english: 'It''s sunny'
      rain:
        lang:
          catalan: 'Plou'
          english: 'It''s raining'
```

Moreover, the following is possible:

```
job:
  awesome_job1: 'this is an awesome job so it has a very long description bla bla'
  awesome_job2: '<<<< awesome_job1 >>>>' # awesome_job2 is very similar to awesome_job1
```

As seen above, option `awesome_job2` of selector `job` will get the contents from option `awesome_job1`, as the variable `<<<< awesome_job1 >>>>` has a string which matches a key in the selection dictionary. This may be useful to avoid having duplicated content.

## Include dependencies

If the final LaTeX document depends on external documents (such as pictures), these are (symbolically) linked so they are available to the LaTeX processor. Note how `pic_portrait` in the `includegraphics` command is in the same directory as the YAML file. The processor will not complain when processing the YAML file, as all the dependencies are linked to its directory.

```
dependencies:
  - '/pictures/pic_portrait.jpg'
  - '../common/fonts' # Do not end with '/', i.e. '../common/fonts/'
  - ...
replace:
  photo: {var: mypic}
vars:
  mypic
    - includegraphics: {opts: ['width=0.15\textwidth'], args: ['pic_portrait.jpg']}
    - ...
```

## Output, command line options and relative paths

Calling `./yaml2latex.py myfile` will create a PDF file in a subdirectory `generated/yyyymmdd/myfile.pdf` (with `myfile_selector1-opt1_selector2-opt2_yyyymmdd.pdf` if there are selectors in the original file) relative to the run directory. The output can be changed by appending the output filename `./yaml2latex.py myfile myfolder/out.tex` or simply `myfolder/out.tex` (extension not taken into account). The template can be specified or overwritten by passing `--template mytemplate.tex`. It can also be stated in the same YAML file with the top-level key `outputdir` (a folder with the current day in `yyyymmdd` format will be created). Selectors are passed as explained above. A PDF is always generated by default using `xelatex`, but this can be specified using `--texconverter`. If no PDF file is desired one can pass the `--no-pdf` flag. See all the options with the `-h` flag.

Files specified in the YAML file are relative to the YAML file. Files specified in the command line are relative to the run directory.

## My YAML file needs to use reserved keywords

If one needs to use a reserved keyword, these can be easily changed by replacing the words in `yaml_fields` or `yaml_reserved` in `yaml2latex.py`. If `"template"` is replaced with `"mytemplate"`, then `yaml2latex` will know that the template is specified with the `"myawesometemplate"` keyword.

```
yaml_fields = {
    "template": "myawesometemplate", # Template field
    ...
}
```

## TODO

This was a one day project, and I use this script for some of my tasks. It works well enough, but may not be up to the standards.

- [ ] Improve parsing and classification (e.g. command vs string vs environment vs reserved)
- [ ] Error handling
- [ ] Classes
- [ ] ...
