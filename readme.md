# Reach Processing Utilities

This repository contains a collection of resources created to extract hydrology center lines from the United States Geological Survey's National Hydrology Dataset representing recreational reaches based on putin and takeout locations using Esri's ArcGIS for Desktop software.

## Contents
This repository contains a Python package located in **whitewater_analysis/utilities** where the analysis logic lives, a few short scripts located in **whitewater_analysis** providing bindings to the top level analysis tasks for the tools contained in the **Whitewater Analysis Tools** toolbox. If you really love digging through Python code, you may find it interesting to dig around in the first two. If all you are interested in is how to get access to the tools, just look in the toolbox.

## Whitewater Analysis Tools Toolbox

The Whitewater Analysis Tools toolbox has one toolset, USGS NHD Acqusition & Aggregation and one tool, Get Reach Hydrolines. The toolset facilitates the process of building out a single NHD dataset for reach analysis from the high resolution NHD subregions available from the USGS.  

## Licensing - Apache License

Copyright 2014 Joel McCune

Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except in compliance with the License. You may obtain a copy of the License at

http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the specific language governing permissions and limitations under the License.