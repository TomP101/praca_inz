cd C:\Users\tomek\praca_inz\terraform

$Root="C:\Users\tomek\praca_inz"
$Tag="latest"
$Region="eu-north-1"
$AccountId="774305577837"

$outs = terraform output -json | ConvertFrom-Json

$cluster  = $outs.ecs_cluster_name.value
$services = $outs.ecs_service_names.value
$repos    = $outs.ecr_repo_urls.value
$alb      = $outs.alb_dns_name.value

cmd.exe /c "aws ecr get-login-password --region $Region | docker login --username AWS --password-stdin $AccountId.dkr.ecr.$Region.amazonaws.com"

$buildPaths = @{
  api        = "$Root\services\task-api-service"
  result     = "$Root\services\result-service"
  dispatcher = "$Root\services\task-dispatcher-service"
  cpu        = "$Root\services\cpu-worker-service"
  memory     = "$Root\services\memory-worker-service"
}

foreach ($k in $repos.PSObject.Properties.Name) {
  $repo = $repos.$k
  $path = $buildPaths[$k]
  if (!(Test-Path $path)) { throw "Brakuje katalogu: $path" }

  docker build -t "$repo`:$Tag" "$path"
  docker push "$repo`:$Tag"
}

$svcList = @(
  $services.api,
  $services.result,
  $services.dispatcher,
  $services.cpu,
  $services.memory
)

foreach ($s in $svcList) {
  aws ecs update-service --region $Region --cluster $cluster --service $s --force-new-deployment | Out-Null
}

"forced redeploy"
"Docs: http://$alb/docs"
"Health: http://$alb/health"
