cron_job = {
    "version": "0",
    "id": "3240d264-fd5f-ff88-af0d-491044c589b8",
    "detail-type": "Scheduled Event",
    "source": "aws.events",
    "account": "043337637715",
    "time": "2022-02-14T03:45:00Z",
    "region": "us-west-2",
    "resources": [
        "arn:aws:events:us-west-2:043337637715:rule/dev-5min-call"
    ],
    "detail": {}
}

sqs_job = {
    "Records": [
        {
            "messageId": "1bfae105-0117-4233-ab0f-226ec63cbccc",
            "receiptHandle": "AQEBbKVFPJsuEoHXEcBBHd1E9BIfg2vLwEFLsIPmMupPSVPk7uU9sNXLeg5llQVHrzBqqoexKqG658/Q9HgCrl6/DLK7ED85WpJf+18MqHl3woTqRllQv39/tbTaL5xZCmWUnRcWgiWnMuKs60NRSkdWpEmTCt8DKhvxJj8x9Uzt918yCA4hkxYN6Izelz7qt2V7JvodTgLHMLkRnpeLK3qGgBSWyM4XCQqGG1APDTAqkTsZ2S0SvktXuMLTGvtOGwJZhGo8QFRHe9F/pmkKi7ERu6Yknfx+Ip4VsPVO/fu7L2XQ3eGq0vuV4o66vDHB2BJ7cOWQnah10E6ZuYEP2JqtnYxhBTtEPNead8B7ZINVu0zD0wgOrUfRZV3ZXVuF6UNnt4xKYa36iyzFcTGnQ9qsUg==",
            "body": '{"start_date": "2005-01-01", "end_date": "2014-12-31", "version": "forex_trader_v2", "option_code": "TF1_MA1_FR1_TM1_PP10_TG1", "symbol": "GBPUSD"}',
            "attributes": {
                "ApproximateReceiveCount": "7",
                "SentTimestamp": "1652507498473",
                "SenderId": "AIDAJQLLF7ZDUA7QHWSGQ",
                "ApproximateFirstReceiveTimestamp": "1652507498473"
            },
            "messageAttributes": {},
            "md5OfBody": "39226dec28b2ed36783b7144cd068d5c",
            "eventSource": "aws:sqs",
            "eventSourceARN": "arn:aws:sqs:us-west-2:043337637715:fx-backtest-request",
            "awsRegion": "us-west-2"
        }
    ]
}
