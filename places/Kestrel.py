owner = [
    # 'EASTHAMPTON CITY OF',
    'KESTREL LAND TRUST',
    # 'COMMONWEALTH OF MASSACHUSETTS',
    ]

# WHERE_CLAUSE = f'''OWNER1 IN ({','.join("'"+x+"'" for x in owner)}) '''
WHERE_CLAUSE = f'''OWNER1 IN ({','.join("'"+x+"'" for x in owner)}) AND CITY = 'EASTHAMPTON' '''
PLACE_NAME = 'Kestrel Land Trust'
OUTPUT_KML = 'Kestrel-Land-Trust.kml'