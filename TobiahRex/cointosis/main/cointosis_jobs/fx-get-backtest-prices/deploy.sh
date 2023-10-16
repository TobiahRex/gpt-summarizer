export AWS_PROFILE=cointosis
echo "AWS_PROFILE="$AWS_PROFILE
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin 043337637715.dkr.ecr.us-west-2.amazonaws.com

docker build --no-cache -t fx-get-backtest-prices .

docker run -v ~/.aws:/root/.aws -e AWS_PROFILE=cointosis fx-get-backtest-prices

docker tag fx-get-backtest-prices:latest 043337637715.dkr.ecr.us-west-2.amazonaws.com/fx-get-backtest-prices:latest
docker tag fx-get-backtest-prices:latest 043337637715.dkr.ecr.us-west-2.amazonaws.com/fx-get-backtest-prices:build_$BUILD_ID

docker push 043337637715.dkr.ecr.us-west-2.amazonaws.com/fx-get-backtest-prices:latest

docker rmi fx-get-backtest-prices:latest
docker rmi 043337637715.dkr.ecr.us-west-2.amazonaws.com/fx-get-backtest-prices:latest

