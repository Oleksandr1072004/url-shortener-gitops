Типові помилки та їх вирішення
Помилка	Причина	Рішення
repository not found	Приватний репозиторій або помилка в URL	Зробіть репозиторій публічним або argocd repo add ...
ImagePullBackOff	Образ приватний або локальний	Зробіть пакет GHCR публічним
values-minikube.yaml: no such file	Неправильний шлях у valueFiles	Шлях має бути відносно path чарту
Application не бачить Argo CD	Application створено не в namespace: argocd	Перевірте metadata.namespace
Зміна не приїхала	Не та гілка або не минув інтервал	Натисніть Refresh в UI або argocd app get --refresh
ComparisonError	Помилка шаблону Helm	Локально перевірте helm template
