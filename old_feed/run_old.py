from flask import Flask, Response
#from old_feed.computation_request import computation_request
from interface import computational_request
from comp_req import comp_req
from flask_cache import Cache
from flask_sockets import Sockets
import time
import ujson
import json

app = Flask(__name__)
cache = Cache(app, config={'CACHE_TYPE': 'simple', 'CACHE_DEFAULT_TIMEOUT': 0})

sockets = Sockets(app)
# socketio = SocketIO(app)

# @socketio.on('get_data_event', namespace='/getdata')

@sockets.route('/getdata')
def feed(websocket):
    message = ujson.loads(websocket.receive())
    measurements = test_measurements()
    print(message)
    data = message['data']
    start = data['start']
    end = data['end']
    chromosome = data['chr']
    gene_name = data['gene']
    seqID = message['seq']
    print ("parameters")
    key = chromosome + '-' + str(start) + '-' + str(end)
    cached = cache.get(key)
    if cached:
        websocket.send(ujson.dumps(cached))
        websocket.send(ujson.dumps(seqID))
        return
    results = computational_request(start, end, chromosome, gene_name, measurements=measurements)
    cache_results = []
    print (results)
    for result in results:
        print ("send back!")
        print (time.time())
        print ("\n")
        # emit('returned_results', result)
        cache_results.extend(result)
        websocket.send(ujson.dumps(result))

    cache.set(key, cache_results)

    websocket.send(ujson.dumps(seqID))


# just for testing purposes
def test_measurements(expression=True, block=True, methylation=True):
    measurements = []
    gene_types = ['breast___normal', 'breast___tumor', 'colon___normal',
                  'colon___tumor', 'lung___normal', 'lung___tumor',
                  'thyroid___normal', 'thyroid___tumor']

    gene_names = ['breast_normal', 'breast_tumor', 'colon_normal',
                  'colon_tumor', 'lung_normal', 'lung_tumor',
                  'thyroid_normal', 'thyroid_tumor']

    tissue_types = ['breast', 'colon', 'thyroid', 'lung']

    methylation_types = ['breast_normal', 'breast_cancer', 'colon_normal',
                         'colon_cancer', 'lung_normal', 'lung_cancer',
                         'thyroid_normal', 'thyroid_cancer']
    if expression:
        for gene_type, gene_name in zip(gene_types, gene_names):
            measurements.append({
                "id": gene_type,
                "name": 'Expression ' + gene_name,
                "type": "feature",
                "datasourceId": "gene_expression_barcode_subtype",
                "datasourceGroup": "gene_expression_barcode_subtype",
                "dataprovider": "umd",
                "formula": None,
                "defaultChartType": "scatterplot",
                "annotation": None,
                "metadata": ["probe"]
            })

    if block:
        for tissue_type in tissue_types:
            measurements.append({
                "id": 'timp2014_' + tissue_type + '_blocks',
                "name": tissue_type + ' blocks',
                "type": "feature",
                "datasourceId": 'timp2014_' + tissue_type + '_blocks',
                "datasourceGroup": 'timp2014_' + tissue_type + '_blocks',
                "dataprovider": "umd",
                "formula": None,
                "defaultChartType": "block",
                "annotation": None,
                "metadata": ["probe"]
            })

    if methylation:
        # for methylation difference
        for tissue_type in tissue_types:
            measurements.append({
                "id": tissue_type,
                "name": 'Collapsed Methylation Diff ' + tissue_type,
                "type": "feature",
                "datasourceId": 'timp2014_collapsed_diff',
                "datasourceGroup": 'timp2014_collapsed_diff',
                "dataprovider": "umd",
                "formula": None,
                "defaultChartType": "line",
                "annotation": None,
                "metadata": ["probe"]
            })

        for methylation_type in methylation_types:
            measurements.append({
                "id": methylation_type,
                "name": ' Average Probe level Meth ' + methylation_type,
                "type": "feature",
                "datasourceId": 'timp2014_probelevel_beta',
                "datasourceGroup": 'timp2014_probelevel_beta',
                "dataprovider": "umd",
                "formula": None,
                "defaultChartType": "line",
                "annotation": None,
                "metadata": []
            })

    return measurements


# road map measurements
def roadmap_measurements(expression=True, block=True, methylation=True):
    measurements = []
    gene_types = ['breast___normal', 'breast___tumor', 'colon___normal',
                  'colon___tumor', 'lung___normal', 'lung___tumor',
                  'thyroid___normal', 'thyroid___tumor']

    tissue_types = ['breast', 'colon', 'thyroid', 'lung']
    if expression:
        for gene_type in gene_types:
            measurements.append({
                "id": gene_type,
                "name": gene_type,
                "type": "feature",
                "datasourceId": "gene_expression_barcode_subtype",
                "datasourceGroup": "gene_expression_barcode_subtype",
                "dataprovider": "umd",
                "formula": None,
                "defaultChartType": "scatterplot",
                "annotation": None,
                "metadata": ["probe"]
            })

    if block:
        for tissue_type in tissue_types:
            measurements.append({
                "id": 'timp2014_' + tissue_type + '_blocks',
                "name": 'timp2014_' + tissue_type + '_blocks',
                "type": "feature",
                "datasourceId": 'timp2014_' + tissue_type + '_blocks',
                "datasourceGroup": 'timp2014_' + tissue_type + '_blocks',
                "dataprovider": "umd",
                "formula": None,
                "defaultChartType": "block",
                "annotation": None,
                "metadata": ["probe"]
            })

    if methylation:
        for tissue_type in tissue_types:
            measurements.append({
                "id": tissue_type,
                "name": tissue_type,
                "type": "feature",
                "datasourceId": 'timp2014_collapsed_diff',
                "datasourceGroup": 'timp2014_collapsed_diff',
                "dataprovider": "umd",
                "formula": None,
                "defaultChartType": "line",
                "annotation": None,
                "metadata": ["probe"]
            })

    return measurements


if __name__ == "__main__":
    from gevent import pywsgi
    from geventwebsocket.handler import WebSocketHandler
    server = pywsgi.WSGIServer(('', 5001), app, handler_class=WebSocketHandler)
    data = ujson.dumps(test_measurements())
    with open('epiviz.json', 'w') as outfile:
        json.dump(test_measurements(), outfile)
    print("Server Starts!")
    server.serve_forever()
