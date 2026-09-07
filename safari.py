'''
Provide users with a list of plants to find in a given area.
Provide botanical name, common name, wikipedia URL (if given), taxon photos w/ attribution.
Include 3 native plants (things to be excited about) and an introduced plant (things to report).
'''

import datetime
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
    # if taxa:
    #     for k,t in taxa.items():
    #         print(f"{t['name']} ({t['preferred_common_name']}) [{t['native']}] x{t['count']} w/ {len(t['photos'])} pics")
        # store taxa in db
else:
    print(f"{response.status_code} - {response.text}")

# pull random taxa from db
import random

safari_id_list = []

native_taxa_ids = [k for k,v in taxa.items() if v['native']]
if native_taxa_ids:
    for i in range(3):
        safari_id_list.append(native_taxa_ids.pop(random.randrange(len(native_taxa_ids))))

introduced_taxa_ids = [k for k,v in taxa.items() if not v['native']]
if introduced_taxa_ids:
    for i in range(1):
        safari_id_list.append(introduced_taxa_ids.pop(random.randrange(len(introduced_taxa_ids))))

safari_list = [v for k,v in taxa.items() if k in safari_id_list]

for s in safari_list:
    print('#'*80)
    print(f"# {s['name']} ({s['preferred_common_name']})")
    print('#'*80)
    print()
    print(f"\t* https://inaturalist.org/taxa/{s['taxon_id']}")
    print(f"\t* {s['wikipedia_url']}")
    print()
    for p in s['photos']:
        print(f"\t* {p['url']}")
        print(f"\t  {p['attribution']}")
    print()
    print()
