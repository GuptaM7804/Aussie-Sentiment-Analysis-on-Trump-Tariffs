FROM jupyter/base-notebook:latest

USER root

COPY requirements-jupyter.txt /home/jovyan/
RUN pip install --no-cache-dir -r /home/jovyan/requirements-jupyter.txt

COPY sentiment-analysis.ipynb /home/jovyan/
COPY analysis_utils.py /home/jovyan/

WORKDIR /home/jovyan

RUN chown -R jovyan:users /home/jovyan

USER jovyan

CMD ["start-notebook.sh", "--NotebookApp.token=''"]