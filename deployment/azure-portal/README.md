# Deploy the SatyaSetu portal on Azure

The template provisions one Ubuntu VM with a managed OS disk. SSH is allowed only from the operator CIDR. The web app binds to loopback and is accessed through an SSH tunnel. Run history and review queues persist on the VM disk under `/var/lib/satyasetu`.

## 1. Provision the VM

Use Azure CLI with an active subscription, a dedicated resource group, and an SSH public key. Choose a region with quota for your VM size. The template defaults to 4 vCPUs and 16 GiB memory for the full survey runs. Azure resources incur charges.

~~~bash
az login
RG=satyasetu-demo
LOCATION=eastus
OPERATOR_CIDR=YOUR_PUBLIC_IPV4/32
az group create --name "$RG" --location "$LOCATION"
az deployment group create --resource-group "$RG" --name satyasetu-portal \
  --template-file deployment/azure-portal/main.bicep \
  --parameters "operatorCidr=$OPERATOR_CIDR" "sshPublicKey=$(cat ~/.ssh/id_ed25519.pub)"
VM_IP=$(az deployment group show --resource-group "$RG" --name satyasetu-portal \
  --query properties.outputs.ipAddress.value -o tsv)
~~~

## 2. Copy the full release and start the app

From the machine that has the downloaded `satyasetu.zip`, copy it to the VM. Verify the SSH host fingerprint using your organization's normal process.

~~~bash
scp satyasetu.zip "azureuser@$VM_IP:~/satyasetu.zip"
ssh "azureuser@$VM_IP"
cloud-init status --wait
unzip -q ~/satyasetu.zip -d ~/satyasetu-release
bash ~/satyasetu-release/satyasetu/deployment/azure-portal/install.sh
curl -fsS http://127.0.0.1:8080/healthz
~~~

If provisioning is complete but dependencies are unavailable, check `cloud-init status --long` before running the installer. View service logs with `sudo journalctl -u satyasetu -n 100`.

## 3. Open the portal

From your local machine, keep the tunnel running:

~~~bash
ssh -N -L 8080:127.0.0.1:8080 "azureuser@$VM_IP"
~~~

Open [http://localhost:8080](http://localhost:8080). Choose **Run small fixture**, **Run claims review**, or **Run 2023–2024 BRFSS**. The ZIP already includes the survey inputs and codebooks.

## Databricks and notifications

To use Azure Databricks separately, authenticate your Databricks CLI and upload the same bundled inputs to an existing Unity Catalog volume:

~~~bash
bash deployment/databricks/upload_inputs.sh dbfs:/Volumes/demo/health/inputs
~~~

Use the returned `brfss` and `claims` subfolders with the [BRFSS notebook guide](../../cloud/databricks/README.md) and [claims notebook guide](../databricks/README.md). The upload script leaves existing files in place and reports a conflict if a target already exists.

Configure [survey ticket notifications](../../cloud/logic_apps/README.md) and [approved claims notifications](../logic-apps/README.md) in Logic Apps if needed. Store the callback URLs in a root-readable `/etc/satyasetu.env` and restart the service. Use the portal's send button only after the connector responds with HTTP 200 following successful delivery. For deployment on a private SSH-only VM, tunnel access provides the access boundary. An optional `SATYASETU_PASSWORD` in the same file adds operator authentication.

## Operating boundary

This configuration supports a private pilot with one portal instance and one Spark job at a time. Keep SQLite on the VM's local managed disk. Back up the state directory with the service stopped or use your managed backup process. Review retention because each full survey run saves its evidence and staged rows. A shared production deployment needs organizational SSO and role enforcement, managed workflow state and compute, backups, and monitoring. The claims inputs and policies in this package are synthetic.

References: [Azure Linux VM Bicep quickstart](https://learn.microsoft.com/en-us/azure/virtual-machines/linux/quick-create-bicep) and [Databricks CLI volume commands](https://learn.microsoft.com/en-us/azure/databricks/dev-tools/cli/reference/fs-commands).
