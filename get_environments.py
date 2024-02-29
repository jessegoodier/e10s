import subprocess
import json
import os

ClusterName = os.getenv("CLUSTER_NAME", "null")

output = {"ClusterName": ClusterName, "Namespaces": []}

def get_namespaces():
    ## If you only want to list pods in namespaces that have ingresses, uncomment these lines and remove the others:
    # namespaces = subprocess.run(["kubectl", "get", "ingress", "--all-namespaces", "-o", "json"], capture_output=True, text=True)
    # namespaces_json = json.loads(namespaces.stdout)
    # namespaces = sorted(set(item.get('metadata', {}).get('namespace') for item in namespaces.get('items', [])))
    # return namespaces

    # Get all namespaces
    namespaces = subprocess.run(["kubectl", "get", "namespaces", "-o", "json"], capture_output=True, text=True)
    namespaces_json = json.loads(namespaces.stdout)
    namespace_names = [item['metadata']['name'] for item in namespaces_json['items']]
    print(f"Processing namespaces: {len(namespace_names)}")
    return namespace_names

def get_ingress(ns):
    # Get all ingress
    ingress = subprocess.run(["kubectl", "get", "ingress", "-n", ns, "-o", "json"], capture_output=True, text=True)
    ingress = json.loads(ingress.stdout)
    ingress = [(rule.get('host'), path.get('path')) for item in ingress.get('items', []) for rule in item.get('spec', {}).get('rules', []) for path in rule.get('http', {}).get('paths', [])]
    return ingress

def get_pods(ns):
    # Get all pods
    try:
        pods = subprocess.run(["kubectl", "get", "pod", "-n", ns, "-o", "json"], capture_output=True, text=True)
        pods = json.loads(pods.stdout)
        pods = [item.get('metadata', {}).get('name') for item in pods.get('items', [])]
        return pods
    except subprocess.CalledProcessError as e:
        print(f"Error occurred while getting pods: {e}")
        return []


def get_container_names_and_status(ns, p):
    # Get all container names and their status
    pod_info = subprocess.run(["kubectl", "get", "pod", "-n", ns, p, "-o", "json"], capture_output=True, text=True)
    pod_info = json.loads(pod_info.stdout)
    containers = pod_info.get('spec', {}).get('containers', [])
    statuses = pod_info.get('status', {}).get('containerStatuses', [])
    container_names_and_status = []
    for container, status in zip(containers, statuses):
        container_names_and_status.append({
            'name': container.get('name'),
            'status': status.get('state')
        })
    return container_names_and_status

def get_container_images(ns, p, cn):
    # Get all container images
    container_images = subprocess.run(["kubectl", "get", "pod", "-n", ns, p, "-o", "jsonpath={.spec.containers[?(@.name=='" + cn + "')].image}"], capture_output=True, text=True)
    return container_images.stdout

namespaces = get_namespaces()

def get_helm_releases(ns):
    # Get all helm releases
    helm_releases = subprocess.run(["helm", "list", "-n", ns, "-o", "json"], capture_output=True, text=True)
    helm_releases = json.loads(helm_releases.stdout)
    # helm_releases = [item.get('name') for item in helm_releases]
    return helm_releases

def manage_configmap():
    print("------------------------\nConfigmap creation and restart web server")
    try:
        delete_cm = subprocess.run(["kubectl", "delete", "configmap", "envs-json", "-n", "e10s"], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error occurred while deleting configmap: {e}\n{delete_cm.stderr}")

    try:
        create_cm = subprocess.run(["kubectl", "create", "configmap", "envs-json", "-n", "e10s", "--from-file", "docs/envs.json"])
    except subprocess.CalledProcessError as e:
        print(f"Error occurred while creating configmap: {e}")

    try:
        restart_pod = subprocess.run(["kubectl", "rollout", "restart", "deployment", "e10s-web", "-n", "e10s"], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error occurred while restarting pod: {e}")


i = 0
for ns in namespaces:
    namespace_data = {"Namespace": ns, "Ingress": [], "Pods": [], "HelmReleases": []}
    ingress = get_ingress(ns)
    i += 1
    print(f"------------------------\nNamepspace: {ns} ({i} of {len(namespaces)})")
    for host, path in ingress:
        namespace_data["Ingress"].append({"Host": host, "Path": path})
    helm_releases = get_helm_releases(ns)
    for release in helm_releases:
        namespace_data["HelmReleases"].append(release)
        print(f"helm release: {release}")
    print("Pods:")
    pods = get_pods(ns)
    for p in pods:
        pod_data = {"Pod": p, "Containers": []}
        print(p)
        container_info = get_container_names_and_status(ns, p)
        for info in container_info:
            container_image = get_container_images(ns, p, info['name'])
            print(info['name'], container_image, info['status'])
            pod_data["Containers"].append({"ContainerName": info['name'], "Image": container_image, "Status": info['status']})
        namespace_data["Pods"].append(pod_data)

    output["Namespaces"].append(namespace_data)

with open("docs/envs.json", "w") as f:
    f.write(json.dumps(output, indent=2))

manage_configmap()

