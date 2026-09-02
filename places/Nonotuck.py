loc_id = [
    'M_103713_889933', # Nonotuck and Mountain View
    'M_103603_889464', # Adjoining town property to the SW
    'M_103868_890539', # Nashawannuck
    'M_104234_890016', # Marsh to S of Nashawannuck
    'M_104539_889413', # more town swamp, farther S
    ]

WHERE_CLAUSE = f'''LOC_ID IN ({','.join("'"+x+"'" for x in loc_id)}) '''
PLACE_NAME = 'Nonotuck Park and Nashawannuck Pond'
OUTPUT_KML = 'Nonotuck-Nashawannuck.kml'