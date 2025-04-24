import json
import os
from tqdm import tqdm

def remove_duplicate_cuis(dir):
    """
    Removes duplicate dictionary items from a JSON list based on the 'cui' key.

    Args:
        json_data: A JSON string or a Python list of dictionaries.

    Returns:
        A list of dictionaries with only unique 'cui' values.  Returns an empty list if input is invalid.
    """

    with open(dir, 'r') as f:
        data = json.load(f)
    
    unique_cuis = set()
    result = []

    for item in data['metamap_result']:
        # Check if the item is a dictionary and has a 'cui' key
        if isinstance(item, dict) and 'cui' in item:
            cui = item['cui']
            if cui not in unique_cuis:
                unique_cuis.add(cui)
                result_item = {
                    "cui": cui,
                    "name": item.get("name"),
                    "group": item.get("group"),
                    "type": item.get("type"),
                    "onco_tag": item.get("onco_tag")
                }
                result.append(result_item)
        else:
            print(f"Skipping invalid item: {item}.  Must be a dictionary with a 'cui' key.")

    new_data = data.copy()
    new_data['metamap_result'] = result

    return new_data



if __name__ == '__main__':
    phase = 'phase2_failed' # phase2_failed phase3_failed phase4_failed
    # phase = 'phase2' #'phase2' # phase3 phase4
    input_root_dir = f'Data/metamap_result/{phase}'
    output_root_dir = f'Data/metamap_result_processed/{phase}'

    # for each json file in input_root_dir, call remove_duplicate_cuis
    json_files = os.listdir(input_root_dir)
    for filename in tqdm(json_files):
        if filename.endswith('.json'):
            input_file_path = os.path.join(input_root_dir, filename)
            output_file_path = os.path.join(output_root_dir, filename)

            # Process the file
            unique_data = remove_duplicate_cuis(input_file_path)

            # Write the unique data to the output file
            with open(output_file_path, 'w') as f:
                json.dump(unique_data, f, indent=4)

            print(f"Processed {filename}: {len(unique_data['metamap_result'])} unique items found.")
