# https://experience.arcgis.com/experience/d72761ca66c44a6bb51e030c569e4f72#data_s=id%3AdataSource_2-19d4fec8759-layer-5%3A2210547&widget_21=active_datasource_id:dataSource_2,center:-8088864.739911023%2C5201632.87718308%2C102100,scale:3133.678109525552,level:17.611570247950027,rotation:0,viewpoint:%7B%22rotation%22%3A0%2C%22scale%22%3A3133.678109525552%2C%22targetGeometry%22%3A%7B%22spatialReference%22%3A%7B%22latestWkid%22%3A3857%2C%22wkid%22%3A102100%7D%2C%22x%22%3A-8088864.739911023%2C%22y%22%3A5201632.87718308%7D%7D
loc_id = [
    'M_103243_891139', # 
    'M_102473_890438', # 
    'M_101922_889979', # 
    'M_103412_891353', # 
    'M_104292_892115', # 
    'M_103838_891780', # 
    'M_104594_892407', # 
    'M_104786_892682', # 
    'M_104786_892682', # 
    'M_104782_893434', # 
    'M_104703_893883', # 
    'M_105170_892422', # 
    'M_105998_892633', # ARTHUR ST EASTHAMPTON, MA  
    'M_106529_892898', # FORT HILL RD EASTHAMPTON, MA  
    'M_107066_893386', # RIVER ST EASTHAMPTON, MA  
    ] # missing Coleman rd section

WHERE_CLAUSE = f'''LOC_ID IN ({','.join("'"+x+"'" for x in loc_id)}) '''
PLACE_NAME = 'Manhan Rail Trail'
OUTPUT_KML = 'Manhan-Rail-Trail.kml'