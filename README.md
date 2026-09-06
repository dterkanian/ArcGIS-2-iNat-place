# Creating iNaturalist places with an ArcGIS database

This script, assembled by ChatGPT :disappointed:, queries an ArcGIS database, such as the Massachusetts tax parcel database, and turns all of the returned parcel geometries into a KML file which can be uploaded into iNaturalist.

This could be useful for people or organizations that want to monitor:
  * Conservation areas
  * Public land
  * Introduced species
  * Vulnerable areas or species
  

## Configuration

### ArcGIS

To configure which ArcGIS database you use, adjust the ```FEATURE_SERVICE_URL``` variable. This variable is split between the base URL on the first line and the service name on the second.

You will need to confirm the input and output ```CRS``` encoding used for geography. The variables here are ```SOURCE_CRS``` which defined the encoding used in the database and ```OUTPUT_CRS``` which defined the encoding of your output. The default provided ```EPSG:4326``` is for longitude and latitude.

### Outputs

Finally, you will need to define which ArcGIS records you want returned, how you want them labeled, and what you want the output file to be called. An example input and output file for the Manhan mixed-used rail trail in Easthampton, MA are provided.

The ```WHERE_CLAUSE``` variable defines an SQL clause for filtering rows. You will need to be familiar with your database contents to decide how to usefully compose this clause. Keep in mind, ArcGIS's SQL is case sensitive for both literals and field names.

Each ```place``` I define in a separate ```.py``` file to import, which must expose the following constants:

  * ```WHERE_CLAUSE``` - the SQL clause for filtering data
  * ```OUTPUT_KML``` - the output KML file name
  * ```PLACE_NAME``` - the placename to embed in the KML file

The ```place``` is then specified on the command line:

```sh
python kml-builder2.py MineralHills
```

...which will load ```./places/MineralHills.py``` and look for those 3 variables.

