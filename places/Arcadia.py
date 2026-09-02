owner = [
    'MASS AUDUBON SOCIETY',
    'MASSACHUSETTS AUDUBON',
    ]

WHERE_CLAUSE = f'''OWNER1 IN ({','.join("'"+x+"'" for x in owner)}) AND CITY IN ('EASTHAMPTON','NORTHAMPTON') '''
PLACE_NAME = 'Massachusetts Audubon Society'
OUTPUT_KML = 'Audubon-Arcadia.kml'