---
title: 'STMTools: Xarray extension for Interferometric SAR data in Space-Time Matrix format'
tags:
  - Python
  - Interferometric
  - Synthetic Aperture Radar
  - InSAR
  - Dask
  - Xarray
authors:
  - name: Ou Ku
    orcid: 0000-0002-5373-5209
    affiliation: 1 
  - name: Fakhereh Alidoost
    orcid: 0000-0001-8407-6472
    affiliation: 1
  - name: Pranav Chandramouli
    orcid: 0000-0002-7896-2969
    affiliation: 1
  - name: Thijs van Lankveld
    orcid: 0009-0001-1147-4813
    affiliation: 1
  - name: Meiert W. Grootes
    orcid: 0000-0002-5733-4795
    affiliation: 1
  - name: Francesco Nattino
    orcid: 0000-0003-3286-0139
    affiliation: 1
  - name: Freek van Leijen
    orcid: 0000-0002-2582-9267
    affiliation: 2
affiliations:
 - name: Netherlands eScience Center, Netherlands
   index: 1
 - name: Delft University of Technology, Netherlands
   index: 2
date: 23 Dec 2024
bibliography: paper.bib
---

## Summary

Interferometry Synthetic Aperture Radar (InSAR) is a commonly used technology for monitoring ground surface deformation in various applications, such as civil-infrastructure stability [@chang2014detection; @chang2017railway], hydrocarbons extraction [@fokker2016application; @ZHANG2022102847]. InSAR observations typically come in the form of tabular datasets, with each row representing a measurement point and columns representing the properties of the measurement point. This format mixes the spatial and temporal dimensions, which makes it challenging to integrate InSAR data with other spatial and/or temporal datasets, such as cadastral data, weather data, etc. 

Researchers have thus proposed the Space-Time Matrix (STM) formalism for InSAR datasets [@Bruna2021; @vanLeijen2021]. This framework consists in a representation of the InSAR data with the spatial and temporal dimensions separated. The STM formalism facilitates the analysis of InSAR data in combination with space- and/or time-dependent datasets from other sources (the "contextual information"), by providing a framework for integrating the contextual data. In the context of ground surface deformation, the framework facilitates the identification of the mechanisms driving deformation.

## Statement of Need

Modern time-series InSAR methods provide millions of observation points in a single dataset. However, interpretation of these datasets is challenging due to the complex and ambiguous nature of InSAR observations. [@hanssen2001radar] Under STM format, contextual information such as temperature, precipitation, and land-use can be integrated with InSAR data. This facilitates a better interpretation of InSAR data, resulting in a reliable and accurate understanding of the mechanisms of ground deformation. [@Bruna2021, @vanLeijen2021]

To facilitate the analysis of InSAR datasets following the STM formalism in Python, we developed the `STMTools` package in Python-- as an extension of `Xarray`-- leveraging `Xarray`'s support for labeled multi-dimensional arrays for the Space-Time dimensions. `STMTools` provides a set of tools to efficiently connect the InSAR data with various contextual information, such as cadastral data and weather data. The Xarray `Dataset` data structure is used to group InSAR data and the contextual information under shared dimension coordinates (space and/or time). By building on Xarray, STMTools can also leverage `Dask` for parallel computing, enabling the processing of large-scale InSAR datasets.

## Main Functionalities

The main functionalities of `STMTools` are summarized as follows:

- [I/O operations](https://tudelftgeodesy.github.io/stmtools/stm_init/)

- [InSAR Operations](https://tudelftgeodesy.github.io/stmtools/operations/)

- [Reorder STM by Morton Ordering](https://tudelftgeodesy.github.io/stmtools/order/)

## Tutorial

We provide the following tutorials, also available as Jupyter notebooks, to demonstrate the functionalities of `STMTools`:

- [Basic operations](https://tudelftgeodesy.github.io/stmtools/notebooks/demo_operations_stm/)

- [Reordering STM by Morton Ordering](https://tudelftgeodesy.github.io/stmtools/notebooks/demo_order_stm/)

## Acknowledgements

The authors express sincere gratitude to the Dutch Research Council (Nederlandse Organisatie voor Wetenschappelijk Onderzoek, NWO) for their generous funding of the `STMTools` development through the Collaboration in Innovative Technologies (CIT 2021) Call, grant NLESC.CIT.2021.006. Special thanks to SURF for providing valuable computational resources for `STMTools` testing via grant EINF-2051, EINF-4287 and EINF-6883.

## References
