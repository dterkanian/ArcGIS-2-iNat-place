loc_id = [
    'M_104431_888710',
    'M_104320_888527',
    'M_104171_888498',
    'M_104506_888383',
    'M_104456_887995',
    'M_104243_887641',
    'M_104633_887538',
    'M_104298_887242',    
    ]

WHERE_CLAUSE = f'''LOC_ID IN ({','.join("'"+x+"'" for x in loc_id)}) '''
PLACE_NAME = 'Easthampton Town Forest'
OUTPUT_KML = 'Easthampton-Town-Forest.kml'
