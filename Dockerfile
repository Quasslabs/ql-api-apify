# Apify Python base image (non-root user `myuser`, workdir /home/myuser).
# See https://docs.apify.com/actors/development/actor-definition/dockerfile
FROM apify/actor-python:3.13

USER myuser

COPY --chown=myuser:myuser requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
 && pip freeze

# Only the runtime package; tests and dev files stay out of the image.
COPY --chown=myuser:myuser ql_actor ./ql_actor
RUN python -m compileall -q ql_actor/

CMD ["python", "-m", "ql_actor"]
