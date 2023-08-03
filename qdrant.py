# -*- coding: utf-8 -*-
"""speed_simil.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1ywcc5Vfotfk9xE0CfGou6xLs9I240txU
"""
from qdrant_client import QdrantClient
from qdrant_client.http import models
from transformers import ViTImageProcessor, ViTModel

from flask import Flask, render_template_string, request, jsonify
app = Flask(__name__)

# ej => curl [IP]:5000
@app.route('/')
def hello():
    return render_template_string('<h1>Hello World!</h1>')

@app.route('/search', methods=['POST'])
def search_text():
    '''
    @example Search
    {
        "query": "juan",
        "collection": "tutu",
        "filters": {
            "should": {
                "values": {
                "nombre": "juan"
                }
            }
        }
    }
    '''
    try:
        # obtenemos el mensaje en el formato que venga, [query|body|json]
        query = request.args.get('query') or request.form.get('query') or request.values.get('query') or request.json.get('query')
        image_path = request.args.get('image_path') or request.form.get('image_path') or request.values.get('image_path') or request.json.get('image_path')
        
        collection = request.args.get('collection') or request.form.get('collection') or request.values.get('collection') or request.json.get('collection')
        filters = request.args.get('filters') or request.form.get('filters') or request.values.get('filters') or request.json.get('filters')
        
        options = request.args.get('options') or request.form.get('options') or request.values.get('options') or request.json.get('options')
        options = options or {}
        
        # si no obtenemos nada del mensaje retornamos 400
        
        # if all(list([query, collection])) == False: 
        #     return jsonify(message="BAD REQUEST", status=400)
        
        if image_path:
            image = Image.open(image_path)
            processor, model = create_proccessor_image()
            vectors = get_embbeding_image(image, processor, model)
            metadata = search(vectors[0], collection_name=collection, filters=filters, options=options)

        else: 
            tokenizer = create_tokenizer()
            vectors = np.array(tokenizer.encode(query)).tolist()
            metadata = search(vectors, collection_name=collection, filters=filters, options=options)
        
        status = 200
        if (any(metadata) == False): status = 404
        return jsonify(
            metadata=metadata,
            status=status
        )
    except Exception as e:
        print(e)
        return jsonify(
        message="Ha ocurrido un error: {}".format(e),
        status=422,
    )

@app.route('/create-collection', methods=['POST'])
def createCollection():
    '''
    @example createCollection
    {
        "collection": "tutu"
    }
    '''
    try:
        collection = request.args.get('collection') or request.form.get('collection') or request.values.get('collection') or request.json.get('collection')
        
        # si no obtenemos nada del mensaje retornamos 400
        if collection == False: 
            return jsonify(message="BAD REQUEST", status=400)
        size_embbending_collection = 384 if collection.lower().split()[0] == 'image' else 768
        create_collection(collection, size_embbending_collection)
        return jsonify(
            message='success',
            status=200
        )
    except Exception as e:
        print(e)
        return jsonify(
        message="Ha ocurrido un error: {}".format(e),
        status=422,
    )

@app.route('/upsert', methods=['POST'])
def createData(): 
    '''
    @example createData
    {
        "collection": "tutu",
        "payload": {
            "id": 3213213,
            "name": "foo",
            "description": "foo",
    }
    '''
    collection = request.args.get('collection') or request.form.get('collection') or request.values.get('collection') or request.json.get('collection')
    payload = request.args.get('payload') or request.form.get('payload') or request.values.get('payload') or request.json.get('payload')
    payload = [payload]
    image_path = request.args.get('image_path') or request.form.get('image_path') or request.values.get('image_path') or request.json.get('image_path')
    print(image_path)
    try:
        # si no obtenemos nada del mensaje retornamos 400
        # if collection == False: 
        #     return jsonify(message="BAD REQUEST", status=400)

        if image_path: create_image_dataframe(payload, collection, image_path)            
        else: create_dataframe(payload, collection)

        return jsonify(
            message='success',
            status=200
        )
    except Exception as e:
        print(e)
        return jsonify(
        message="Ha ocurrido un error: {}".format(e),
        status=422,
    )

import pandas as pd
import numpy as np
import pickle as pk
import torch
from tqdm import tqdm
from PIL import Image

def create_proccessor_image():
    processor = ViTImageProcessor.from_pretrained('facebook/dino-vits16')
    model = ViTModel.from_pretrained('facebook/dino-vits16')

    return processor, model

def get_embbeding_image (image, processor, model):
    inputs = processor(images=image, return_tensors="pt")
    with torch.no_grad():
        outputs = model(**inputs).last_hidden_state.mean(dim=1).cpu().numpy()
        
    return outputs

def create_image_dataframe(d: any, collection_name: str, path_image: str):
    print("Creating dataframe")
    try:
        df = pd.DataFrame.from_dict(d)
        image = Image.open(path_image)
        processor, model = create_proccessor_image()
        vectors = get_embbeding_image(image, processor, model)
        chunk = create_chunk(df)
        upsert_payload(chunk, collection_name, vectors)
    except Exception as e:
        print("Error: " + str(e))
        return e

def create_dataframe(d: any, collection_name: str):
    print("Creating dataframe")
    try:
        df = pd.DataFrame.from_dict(d)
        chunksize = 10 ** 4
        tokenizer = create_tokenizer()
        # df = pd.read_csv(path, sep=";")
        chunk = create_chunk(df)
        vectors = vectorize(chunk, tokenizer=tokenizer)
        upsert_payload(chunk, collection_name, vectors)
    except Exception as e:
        print("Error: " + str(e))
        return e
            

def create_chunk(df):
    print("creatating chunk")
    # text = []
    df['text'] = df.apply(lambda row: [str(row[column]) for column in df.columns], axis=1)
    df['text'] = df.text.apply(lambda x: ' '.join(x))
    print('len df', len(df))
    return df

def create_tokenizer(checkpoint: str = "hackathon-pln-es/paraphrase-spanish-distilroberta"):
    print("Creating tokenizer...")
    # from sentence_transformers import SentenceTransformer
    from fast_sentence_transformers import FastSentenceTransformer as SentenceTransformer
    # tokenizer = SentenceTransformer(model_name_or_path=checkpoint,
    # device="cpu")
    # return tokenizer
    return SentenceTransformer(
        checkpoint,
        quantize=True,
        cache_folder='./tmp',
        enable_overwrite=True,
        device="cuda"
        if torch.cuda.is_available()
        else "mps"
        if torch.backends.mps.is_available()
        else "cpu",
    )


def vectorize(df, tokenizer):
    print("Creating vectorizer")
    vectors = []
    batch_size = 2048
    batch = []
    df_dict = df.to_dict('records')
    
    for row in tqdm(df_dict):
        batch.append(row['text'])

        if len(batch) >= batch_size:
            vectors.append(tokenizer.encode(batch))
            batch = []

    if len(batch) > 0:
        vectors.append(tokenizer.encode(batch))
        batch = []

    return np.concatenate(vectors)


def create_collection(collection_name: str, size=768) -> None:
    print("Creating collection")
    client.recreate_collection(
        collection_name=collection_name,
        vectors_config=models.VectorParams(size=size, distance=models.Distance.COSINE),
        optimizers_config=models.OptimizersConfigDiff(memmap_threshold=20000),
        hnsw_config=models.HnswConfigDiff(on_disk=True, m=28,
        ef_construct=256, full_scan_threshold=10000),
        quantization_config=models.ScalarQuantization(
            scalar=models.ScalarQuantizationConfig(
                type=models.ScalarType.INT8,
                ignore=False,
                rescore=True,
                quantile=.9,
                always_ram=False,
            ),
        )
    )

    client.create_payload_index(
        collection_name=collection_name,
        field_name="text",
        field_schema=models.TextIndexParams(
            type="text",
            tokenizer=models.TokenizerType.WORD,
            min_token_len=2,
            max_token_len=512,
            lowercase=True,
        )
    )


def update_collection(collection_name: str, tokenizer) -> None:
    client.update_collection(
        collection_name=collection_name,
        # vectors_config=models.VectorParams(size=tokenizer.get_sentence_embedding_dimension(), distance=models.Distance.COSINE),
        optimizers_config=models.OptimizersConfigDiff(memmap_threshold=20000),
        hnsw_config=models.HnswConfigDiff(on_disk=True, m=16,
        ef_construct=512, full_scan_threshold=10000),
        quantization_config=models.ScalarQuantization(
            scalar=models.ScalarQuantizationConfig(
                type=models.ScalarType.INT8,
                # ignore=False,
                rescore=False,
                quantile=.99,
                always_ram=True,
            ),
        )
    )



def create_payload(df):
    payloads = []

    for _, row in df.iterrows():
        payloads.append({
                column: str(row[column]) for column in df.columns
                })

    return payloads


def upsert_payload(df, collection_name: str, vectors):
    payloads = create_payload(df)
    client.upsert(
    collection_name=collection_name,
    points=models.Batch(
        ids=[int(payload['id']) for payload in payloads],
        payloads=payloads,
        vectors=[v.tolist() for v in vectors],
    ),
)


def search(vectors, collection_name: str, filters: dict, options: dict):
    must = filters_must(filters)
    should = filters_should(filters)
    must_not = filters_must_not(filters)
    res = client.search(
        query_vector=vectors, 
        collection_name=collection_name,
        score_threshold=options['score_threshold'] if 'score_threshold' in options else .7, 
        limit=options['limit'] if 'limit' in options else 10,
        append_payload=True, 
        with_vectors=False,
        search_params=models.SearchParams(
            hnsw_ef=128,
            exact=True,
            quantization=models.QuantizationSearchParams(
                # ignore=False,
                rescore=False,
                quantile=.99,
                always_ram=True,
        )),
        query_filter=models.Filter(
            must=must,
            should=should,
            must_not=must_not
        ) if all(filters) else None
    )
    
    payloads = {}
    
    for scored_point in res:
        id, version, score, payload, vector = scored_point
        id_key, id_value = id
        version_key, version_value = version
        score_key, score_value = score
        payload_key, payload_value = payload
        # description = payload_value['description']
        # payload_id = payload_value['id']
        name = payload_value['name']
        # text = payload_value['text']
        # print(f"id: {id}, version: {version}, score: {score}, payload: {payload}")
        
        payloads[f'{id_value}'] = {
            "id": id_value,
            "version": version_value,
            "score": score_value,
            "payload": payload_value
        }
    payloads = sorted(payloads.values(), key=lambda x: x['score'], reverse=True)[:2]
    return payloads

def filters_must(filters: dict):
    must = list()
    if 'must' in filters and 'texts' in filters['must']:
        for key, text in filters['must']['texts'].items():
            must.append(
                    models.FieldCondition(
                        key=str(key), 
                        match=models.MatchText(text=str(text))
                )  
            )

    if 'must' in filters and 'values' in filters['must']:
        for key, value in filters['must']['values'].items():
            must.append(
                models.FieldCondition(
                    key=str(key), 
                    match=models.MatchValue(value=str(value))
                ) 
            )
    return must if len(must) > 0 else None

def filters_must_not(filters: dict):
    must_not = list()
    if 'must_not' in filters and 'texts' in filters['must_not']:
        for key, text in filters['must_not']['texts'].items():
            must_not.append(
                    models.FieldCondition(
                        key=str(key), 
                        match=models.MatchText(text=str(text))
                )  
            )

    if 'must_not' in filters and 'values' in filters['must_not']:
        for key, value in filters['must_not']['values'].items():
            must_not.append(
                models.FieldCondition(
                    key=str(key), 
                    match=models.MatchValue(value=str(value))
                ) 
            )
    return must_not if len(must_not) > 0 else None

def filters_should(filters: dict):
    should = list()
    if 'should' in filters and 'texts' in filters['should']:
        for key, text in filters['should']['texts'].items():
            should.append(
                    models.FieldCondition(
                        key=str(key), 
                        match=models.MatchText(text=str(text))
                )  
            )

    if 'should' in filters and 'values' in filters['should']:
        for key, value in filters['should']['values'].items():
            should.append(
                models.FieldCondition(
                    key=str(key), 
                    match=models.MatchValue(value=str(value))
                ) 
            )
    return should if len(should) > 0 else None

if __name__ == '__main__':
    client = QdrantClient(
        url="http://localhost:6333",
    )
    
    app.run(host='0.0.0.0', debug=False, threaded=True)