'''
Provide users with a list of plants to find in a given area.
Provide botanical name, common name, wikipedia URL (if given), taxon photos w/ attribution.
Include 3 native plants (things to be excited about) and an introduced plant (things to report).
'''

import datetime
import json
import random
import requests

month_number = datetime.date.today().month
last_month_number = (month_number + 11) % 12

# is_native = 'true'
place_id = 239199 # Manhan Rail Trail~Easthampton
month_csv = ','.join([str(last_month_number), str(month_number)])
fields = "all"
fields = "taxon.native,taxon.name,taxon.preferred_common_name,taxon.wikipedia_url,photos.attribution,photos.url"


# url = f"https://api.inaturalist.org/v2/observations?native={is_native}&verifiable=true&place_id={place_id}&month={month_csv}&iconic_taxa=Plantae&expected_nearby=true&fields={fields}"
url = f"https://api.inaturalist.org/v2/observations?verifiable=true&place_id={place_id}&month={month_csv}&iconic_taxa=Plantae&expected_nearby=true&fields={fields}"

response = requests.get(url)
# response = requests.post(url, json=request_json, headers=headers)
if response.status_code == 200:
    taxa = {}
    data = response.json()
    if 'results' in data.keys():
        # print('Parsing results...')
        for d in data['results']:
            taxon_id = d['taxon']['id']
            # print(f'Result taxon id: {taxon_id}')
            if taxon_id in taxa.keys():
                # print("Exists, incrementing")
                taxa[taxon_id]['count'] += 1
            else:
                # print('New, creating')
                taxa[taxon_id] = {
                    'count': 1, 
                    'name': d['taxon']['name'], 
                    'native': d['taxon']['native'],
                    'photos': [],
                    'preferred_common_name': d['taxon']['preferred_common_name'],
                    'taxon_id': taxon_id,
                    'wikipedia_url': d['taxon']['wikipedia_url'],
                    }
            for p in d['photos']:
                # print('Attaching photos')
                taxa[taxon_id]['photos'].append({
                    'attribution': p['attribution'],
                    'url': p['url'],
                })
    if taxa:
        taxa_list = [v for k,v in taxa.items()]
        with open("taxa.json", "w", encoding="utf-8") as file:
            json.dump(taxa_list, file, indent=4)
else:
    print(f"{response.status_code} - {response.text}")
