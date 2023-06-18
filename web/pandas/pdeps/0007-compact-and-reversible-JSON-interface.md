# PDEP-7: Compact and reversible JSON interface

- Created: 16 June 2023
- Status: Under discussions
- Discussion: [#53252](https://github.com/pandas-dev/pandas/issues/53252)
- Author: [Philippe THOMY](https://github.com/loco-philippe) 
- Revision: 1


#### Summary
- [Abstract](./pandas_PDEP.md/#Abstract)
    - [Problem description](./pandas_PDEP.md/#Problem-description)
    - [Feature Description](./pandas_PDEP.md/#Feature-Description)
- [Scope](./pandas_PDEP.md/#Scope)
- [Motivation](./pandas_PDEP.md/#Motivation)
    - [Why is it important to have a compact and reversible JSON interface ?](./pandas_PDEP.md/#Why-is-it-important-to-have-a-compact-and-reversible-JSON-interface-?)
    - [Is it relevant to take an extended type into account ?](./pandas_PDEP.md/#Is-it-relevant-to-take-an-extended-type-into-account-?)
- [Description](./pandas_PDEP.md/#Description)
    - [data typing](./pandas_PDEP.md/#Data-typing)
    - [JSON format](./pandas_PDEP.md/#JSON-format)
    - [Conversion](./pandas_PDEP.md/#Conversion)
- [Usage and impact](./pandas_PDEP.md/#Usage-and-impact)
    - [Usage](./pandas_PDEP.md/#Usage)
    - [Compatibility](./pandas_PDEP.md/#Compatibility)
    - [Impacts on the pandas framework](./pandas_PDEP.md/#Impacts-on-the-pandas-framework)
    - [Risk to do / risk not to do](./pandas_PDEP.md/#Risk-to-do-/-risk-not-to-do)
- [Implementation](./pandas_PDEP.md/#Implementation)
    - [Modules](./pandas_PDEP.md/#Modules)
    - [Implementation options](./pandas_PDEP.md/#Implementation-options)
- [F.A.Q.](./pandas_PDEP.md/#F.A.Q.)
- [Core team decision](./pandas_PDEP.md/#Core-team-decision)
- [Timeline](./pandas_PDEP.md/#Timeline)
- [PDEP history](./pandas_PDEP.md/#PDEP-history)
------------------------- 
## Abstract

### Problem description
The `dtype` is not explicitely taken into account in the current JSON interface.
To work around this problem, a data schema (e.g. `TableSchema`) must be associated with the JSON file.
     
Nevertheless, the current JSON interface is not reversible and has inconsistencies related to the consideration of the `dtype`.

Some JSON-interface problems are detailed in the [linked NoteBook](https://nbviewer.org/github/loco-philippe/NTV/blob/main/example/example_pandas.ipynb#1---Current-Json-interface)


### Feature Description
To have a simple, compact and reversible solution, I propose to use the [JSON-NTV format (Named and Typed Value)](https://github.com/loco-philippe/NTV#readme) - which integrates the notion of type - and its JSON-TAB variation for tabular data.
     
This solution allows to include a large number of types (not necessarily pandas `dtype`).

In the example below, a DataFrame with several data types is converted to JSON. 
The DataFrame resulting from this JSON is identical to the initial DataFrame (reversibility).
With the existing JSON interface, this conversion is not possible.

*data example*
```python
In [1]: from shapely.geometry import Point
        from datetime import date

In [2]: data = {'index':           [100, 200, 300, 400, 500, 600],
                'dates::date':     pd.Series([date(1964,1,1), date(1985,2,5), date(2022,1,21), date(1964,1,1), date(1985,2,5), date(2022,1,21)]), 
                'value':           [10, 10, 20, 20, 30, 30],
                'value32':         pd.Series([12, 12, 22, 22, 32, 32], dtype='int32'),
                'res':             [10, 20, 30, 10, 20, 30],
                'coord::point':    pd.Series([Point(1,2), Point(3,4), Point(5,6), Point(7,8), Point(3,4), Point(5,6)]),
                'names':           pd.Series(['john', 'eric', 'judith', 'mila', 'hector', 'maria'], dtype='string'),
                'unique':          True }

In [3]: df = pd.DataFrame(data).set_index('index')

In [4]: df
Out[4]: 
              dates::date  value  value32  res coord::point   names  unique
        index                                                              
        100    1964-01-01     10       12   10  POINT (1 2)    john    True
        200    1985-02-05     10       12   20  POINT (3 4)    eric    True
        300    2022-01-21     20       22   30  POINT (5 6)  judith    True
        400    1964-01-01     20       22   10  POINT (7 8)    mila    True
        500    1985-02-05     30       32   20  POINT (3 4)  hector    True
        600    2022-01-21     30       32   30  POINT (5 6)   maria    True
```

*JSON representation*

```python
In [5]: df_json = Ntv.obj(df)
        pprint(df_json.to_obj(), compact=True, width=120)
Out[5]: 
        {':tab': {'coord::point': [[1.0, 2.0], [3.0, 4.0], [5.0, 6.0], [7.0, 8.0], [3.0, 4.0], [5.0, 6.0]],
                  'dates::date': ['1964-01-01', '1985-02-05', '2022-01-21', '1964-01-01', '1985-02-05', '2022-01-21'],
                  'index': [100, 200, 300, 400, 500, 600],
                  'names::string': ['john', 'eric', 'judith', 'mila', 'hector', 'maria'],
                  'res': [10, 20, 30, 10, 20, 30],
                  'unique': [True, True, True, True, True, True],
                  'value': [10, 10, 20, 20, 30, 30],
                  'value32::int32': [12, 12, 22, 22, 32, 32]}}
```


*Reversibility*

```python
In [5]: df_from_json = df_json.to_obj(format='obj')
        print('df created from JSON is equal to initial df ? ', df_from_json.equals(df))

Out[5]: df created from JSON is equal to initial df ?  True
```
Several other examples are provided in the [linked NoteBook](https://nbviewer.org/github/loco-philippe/NTV/blob/main/example/example_pandas.ipynb#2---Series)

## Scope
The objective is to make available the proposed JSON interface for any type of data.
    
The proposed interface is compatible with existing data.

## Motivation

### Why is it important to have a compact and reversible JSON interface ?
- a reversible interface provides an exchange format.
- a textual exchange format facilitates exchanges between platforms (e.g. OpenData)
- a JSON exchange format can be used at API level

### Is it relevant to take an extended type into account ?
- it avoids the addition of an additional data schema
- it increases the semantic scope of the data processed by pandas
- the use of a complementary type avoids having to modify the pandas data model


## Description

The proposed solution is based on several key points:
- data typing
- JSON format for tabular data
- conversion to and from JSON format

### Data typing
Data types are defined and managed in the NTV project (name, JSON encoder and decoder).

Pandas `dtype` are compatible with NTV types :

| **pandas  dtype**  | **NTV type**   |
|--------------------|------------|
| intxx              | intxx      |
| uintxx             | uintxx     |
| floatxx            | floatxx    |
| datetime[ns]       | datetime   |
| datetime[ns, <tz>] | datetimetz |
| timedelta[ns]      | durationiso|
| string             | string     |
| boolean            | boolean    |

Note:
- datetime with timezone is a single NTV type (string ISO8601)
- `CategoricalDtype` and `SparseDtype` are included in the tabular JSON format
- `object` `dtype` is depending on the context (see below)
- `PeriodDtype` and `IntervalDtype` are to be defined

JSON types (implicit or explicit) are converted in `dtype` following pandas JSON interface:

| **JSON type**  | **pandas  dtype** |
|----------------|-------------------|
| number         | int64 / float64   |
| string         | string / object   |
| array          | object            |
| object         | object            |
| true, false    | boolean           |
| null           | NaT / NaN / None  |

Note:
- if an NTV type is defined, the `dtype` is ajusted accordingly
- the consideration of null type data needs to be clarified

The other NTV types are associated with `object` `dtype`.
        
### JSON format
The JSON format is defined in [JSON-TAB](https://github.com/loco-philippe/NTV/blob/main/documentation/JSON-TAB-standard.pdf) specification.
It includes the naming rules originally defined in the [JSON-ND project](https://github.com/glenkleidon/JSON-ND) and support for categorical data.    
The specification have to be updated to include sparse data.

### Conversion
When data is associated with a non-`object` `dtype`, pandas conversion methods are used.     
Otherwise, NTV conversion is used.
        
#### pandas -> JSON
- `NTV type` is not defined : use `to_json()`
- `NTV type` is defined and `dtype` is not `object` : use `to_json()`
- `NTV type` is defined and `dtype` is `object` : use NTV conversion

#### JSON -> pandas
- `NTV type` is compatible with a `dtype` : use `read_json()`
- `NTV type` is not compatible with a `dtype` : use NTV conversion
        
## Usage and Impact
        
### Usage
It seems to me that this proposal responds to important issues:
- having an efficient text format for data exchange 
    
    The alternative CSV format is not reversible and obsolete (last revision in 2005). Current CSV tools do not comply with the standard.
    
- taking into account "semantic" data in pandas objects

### Compatibility
Interface can be used without NTV type (compatibility with existing data - [see examples](https://nbviewer.org/github/loco-philippe/NTV/blob/main/example/example_pandas.ipynb#4---Annexe-:-Series-tests))
   
If the interface is available, throw a new `orient` option in the JSON interface, the use of the feature is decoupled from the other features.
        
### Impacts on the pandas framework
Initially, the impacts are very limited:
- modification of the `name` of `Series` or `DataFrame columns` (no functional impact),
- added an option in the Json interface (e.g. `orient='ntv'`) and added associated methods (no functionnal interference with the other methods)

In later stages, several developments could be considered:
- validation of the `name` of `Series` or `DataFrame columns` ,
- management of the NTV type as a "complementary-object-dtype"
- functional extensions depending on the NTV type

### Risk to do / risk not to do
The JSON-NTV format and the JSON-TAB format are not (yet) recognized and used formats. The risk for pandas is that this function is not used (no functional impacts).    
    
On the other hand, the early use by pandas will allow a better consideration of the expectations and needs of pandas as well as a reflection on the evolution of the types supported by pandas.
    
## Implementation

### Modules
Two modules are defined for NTV:
    
- json-ntv
    
    this module manages NTV data without dependency to another module
    
- ntvconnector
    
    those modules manage the conversion between objects and JSON data. They have dependency with objects modules (e.g. connectors with shapely location have dependency with shapely).     
     
The pandas integration of the JSON interface requires importing only the json-ntv module.

### Implementation options
The interface can be implemented as NTV connector (`SeriesConnector` and `DataFrameConnector`) and as a new pandas JSON interface `orient` option.
```mermaid
flowchart TB
    subgraph H [conversion pandas-NTV]
        direction LR
        K(mapping NTV type / dtype\n<i>NTV / pandas</i>) ~~~ I(object dtype conversion\n<i>NTV Connector</i>)
        I ~~~ J(non-object dtype conversion\n<i>pandas</i>)
    end
    
        direction TB
        D{{pandas}} ~~~ F(interface JSON\n<i>pandas</i>)
        E{{NTV}} ~~~ G(pandas NTV Connector\n<i>NTV</i>) 
        F --> H
        G --> H
```
Several pandas implementations are possible:
    
1. External:
    
    In this implementation, the interface is available only in the NTV side.    
    This option means that this evolution of the JSON interface is not useful or strategic for pandas.
    
2. NTV side:
    
    In this implementation, the interface is available in the both sides and the conversion is located inside NTV.    
    This option is the one that minimizes the impacts on the pandas side
    
3. pandas side:
    
    In this implementation, the interface is available in the both sides and the conversion is located inside pandas.    
    This option allows pandas to keep control of this evolution
    
4. pandas restricted:
    
    In this implementation, the pandas interface and the conversion are located inside pandas and only for non-object `dtype`.     
    This option makes it possible to offer a compact and reversible interface while prohibiting the introduction of types incompatible with the existing `dtype`

## F.A.Q.

Tbd

## Core team decision
Implementation option : xxxx
    
## Timeline
Tbd

## PDEP History

- 16 June 2023: Initial draft
