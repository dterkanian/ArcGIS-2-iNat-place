owner = [
    'WILLISTON NORTHAMPTON SCHOOL',
    ]

WHERE_CLAUSE = f'''OWNER1 IN ({','.join("'"+x+"'" for x in owner)}) '''
# WHERE_CLAUSE = f'''OWNER1 IN ({','.join("'"+x+"'" for x in owner)}) AND CITY = 'EASTHAMPTON' '''
PLACE_NAME = 'Williston Northampton School'
OUTPUT_KML = 'Williston-Northampton-School.kml'