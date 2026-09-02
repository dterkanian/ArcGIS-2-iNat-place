owner = [
    'PASCOMMUCK CONS TRUST INC',
    ]

WHERE_CLAUSE = f'''OWNER1 IN ({','.join("'"+x+"'" for x in owner)}) AND CITY = 'EASTHAMPTON' '''
PLACE_NAME = 'Pascommuck Conservation Trust'
OUTPUT_KML = 'Pascommuck.kml'