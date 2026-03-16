from flask import Flask, jsonify, request
from converter import LawConverter

app = Flask(__name__, static_folder='frontend', static_url_path='')
converter = LawConverter('bns_ipc_mapping.json')

if not converter.mapping_data:
    raise SystemExit("Conversion data file 'bns_ipc_mapping.json' could not be loaded.")


def _search_subject(keyword):
    keyword = keyword.strip()
    if not keyword:
        return []

    matches = []
    lower_kw = keyword.lower()

    for item in converter.mapping_data:
        if lower_kw in item.get('subject', '').lower():
            matches.append(_serialize(item))

    return matches


def _serialize(item):
    return {
        'ipc_section': item.get('ipc_section', ''),
        'bns_section': item.get('bns_section', ''),
        'subject': item.get('subject', ''),
    }


@app.route('/')
def index():
    return app.send_static_file('index.html')


@app.route('/api/search', methods=['POST'])
def api_search():
    payload = request.get_json(force=True)
    mode = payload.get('mode')
    query = str(payload.get('query', '')).strip()

    if not query:
        return jsonify(error='Query input is required.'), 400

    if mode == 'ipc':
        results = converter.find_by_field('ipc_section', query)
    elif mode == 'bns':
        results = converter.find_by_field('bns_section', query)
    elif mode == 'subject':
        results = _search_subject(query)
    else:
        return jsonify(error='Unknown search mode.'), 400

    serialized = [_serialize(item) for item in results]
    return jsonify(results=serialized, count=len(serialized))


if __name__ == '__main__':
    app.run(debug=True)
