export AWS_PROFILE=cointosis
echo "AWS_PROFILE="$AWS_PROFILE
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin 043337637715.dkr.ecr.us-west-2.amazonaws.com

docker build --no-cache -t fx-get-backtest-requests .

docker run -v ~/.aws:/root/.aws -e AWS_PROFILE=cointosis fx-get-backtest-requests

docker tag fx-get-backtest-requests:latest 043337637715.dkr.ecr.us-west-2.amazonaws.com/fx-get-backtest-requests:latest
docker tag fx-get-backtest-requests:latest 043337637715.dkr.ecr.us-west-2.amazonaws.com/fx-get-backtest-requests:build_$BUILD_ID

docker push 043337637715.dkr.ecr.us-west-2.amazonaws.com/fx-get-backtest-requests:latest

docker rmi fx-get-backtest-requests:latest
docker rmi 043337637715.dkr.ecr.us-west-2.amazonaws.com/fx-get-backtest-requests:latest

