owner = [
    'MT TOM BOARD OF',
    ]

WHERE_CLAUSE = f'''OWNER1 IN ({','.join("'"+x+"'" for x in owner)}) '''
PLACE_NAME = 'Mt. Tom Reservation'
OUTPUT_KML = 'Mt-Tom-Reservation.kml'