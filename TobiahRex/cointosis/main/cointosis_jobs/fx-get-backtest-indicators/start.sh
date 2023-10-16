#! /bin/bash
if [ $ECS_CONTAINER_METADATA_URI_V4 ]; then
    echo "Getting Task ID..."
    METADATA=$(curl ${ECS_CONTAINER_METADATA_URI_V4}/task)
    python3 -c "import json; meta=json.loads('$METADATA'); task_id=meta['TaskARN'].split('/')[-1]; print(task_id)" > ./task_id
    TASK_ID=$(cat ./task_id)
    export TASK_ID
fi
python main.py