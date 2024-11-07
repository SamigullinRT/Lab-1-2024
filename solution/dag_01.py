from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import pandas as pd
from elasticsearch import Elasticsearch
import os
import uuid

# Пути к файлам
INPUT_PATH = '/opt/airflow/data/input'
OUTPUT_PATH = '/opt/airflow/data/output'

# Настройки подключения к ElasticSearch
ES_HOST = 'elasticsearch-kibana'
ES_PORT = 9200
ES_INDEX = 'dag_wines'

import pandas as pd
import os

def process_data():
    # Получаем список всех .csv файлов в директории INPUT_PATH
    csv_files = [f for f in os.listdir(INPUT_PATH) if f.endswith('.csv')]
    
    if not csv_files:
        print(f"Error: No CSV files found in the input directory: {INPUT_PATH}")
        return

    print(f"Found {len(csv_files)} CSV files: {csv_files}")

    result_dataframe = pd.DataFrame()

    for file in csv_files:
        file_path = os.path.join(INPUT_PATH, file)
        print(f"\nProcessing file: {file}")
        
        # Чтение CSV файла
        try:
            df = pd.read_csv(file_path, low_memory=False)
            print(f"Initial shape of {file}: {df.shape}")
            result_dataframe = pd.concat([result_dataframe, df], ignore_index=True)
        except Exception as e:
            print(f"Error reading {file}: {str(e)}")

    if result_dataframe.empty:
        print("Error: No data was read from the CSV files.")
        return

    print(f"\nShape of the combined dataframe: {result_dataframe.shape}")

    # Обработка данных
    print("Processing data...")
    
    # 1. Удаляем строки, где designation и region_1 не null
    result_dataframe = result_dataframe[
        (result_dataframe['designation'].isnull()) & 
        (result_dataframe['region_1'].isnull())
    ]
    print(f"Shape after removing rows with non-null designation and region_1: {result_dataframe.shape}")

    # 2. Заменяем null значения в столбце price на 0.0
    result_dataframe['price'] = result_dataframe['price'].fillna(0.0)
    print("Replaced null values in 'price' column with 0.0")

    # Дополнительная статистика
    print(f"\nFinal shape of the data: {result_dataframe.shape}")
    print(f"Average price after processing: {result_dataframe['price'].mean():.2f}")
    print(f"Average points after processing: {result_dataframe['points'].mean():.2f}")

    # Сохранение в итоговую таблицу
    output_file = os.path.join(OUTPUT_PATH, 'processed_wine_data.csv')
    result_dataframe.to_csv(output_file, index=False)
    
    print(f"\nProcessed and saved: {output_file}")
    print(f"Columns in the processed dataframe: {result_dataframe.columns.tolist()}")

    return None

def load_data_to_elastic():
    # Подключение к ElasticSearch
    es = Elasticsearch([f'http://{ES_HOST}:{ES_PORT}'])
    
    # Чтение обработанных данных
    df = pd.read_csv(os.path.join(OUTPUT_PATH, 'processed_wine_data.csv'))

    # Заполнение пустых значений
    df = df.fillna('')
    
    # Сохранение каждой строки в ElasticSearch
    for _, row in df.iterrows():
        doc = row.to_dict()
        id_documenta = str(uuid.uuid4())
        es.index(index=ES_INDEX, id=id_documenta, body=doc)
    
    print("Data loaded to ElasticSearch")

# Определение DAG
default_args = {
    'owner': 'darti',
    'depends_on_past': False,
    'start_date': datetime(2024, 12, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'wine_data_processing',
    default_args=default_args,
    description='A DAG to process wine data',
    schedule_interval=None,
    catchup=False,
)

# Определение задач
process_task = PythonOperator(
    task_id='process_wine_data',
    python_callable=process_data,
    dag=dag,
)

load_task = PythonOperator(
    task_id='load_data_to_elastic',
    python_callable=load_data_to_elastic,
    dag=dag,
)

# Определение порядка выполнения задач
process_task >> load_task
