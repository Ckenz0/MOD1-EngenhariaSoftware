param resourcePrefix string
param location string
param frontendLocation string

var services = ['auth', 'projects', 'backlog']

resource logs 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: '${resourcePrefix}-logs'
  location: location
  properties: {
    retentionInDays: 30
    sku: { name: 'PerGB2018' }
  }
}

resource environment 'Microsoft.App/managedEnvironments@2025-01-01' = {
  name: '${resourcePrefix}-env'
  location: location
  properties: {
    workloadProfiles: [{ name: 'Consumption', workloadProfileType: 'Consumption' }]
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logs.properties.customerId
        sharedKey: logs.listKeys().primarySharedKey
      }
    }
  }
}

resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: 'acr${uniqueString(resourceGroup().id)}'
  location: location
  sku: { name: 'Basic' }
  properties: { adminUserEnabled: false, publicNetworkAccess: 'Enabled' }
}

resource vault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: 'kv-${uniqueString(resourceGroup().id)}'
  location: location
  properties: {
    tenantId: tenant().tenantId
    sku: { family: 'A', name: 'standard' }
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
    publicNetworkAccess: 'Enabled'
    accessPolicies: []
  }
}

resource identities 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = [for service in services: {
  name: '${resourcePrefix}-${service}-id'
  location: location
}]

resource pullGrants 'Microsoft.Authorization/roleAssignments@2022-04-01' = [for (service, i) in services: {
  name: guid(registry.id, identities[i].id, 'AcrPull')
  scope: registry
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
    principalId: identities[i].properties.principalId
    principalType: 'ServicePrincipal'
  }
}]

resource frontend 'Microsoft.Web/staticSites@2023-12-01' = {
  name: '${resourcePrefix}-web'
  location: frontendLocation
  sku: { name: 'Free', tier: 'Free' }
  properties: {
    provider: 'Custom'
    stagingEnvironmentPolicy: 'Disabled'
    publicNetworkAccess: 'Enabled'
  }
}

output environmentName string = environment.name
output registryName string = registry.name
output registryServer string = registry.properties.loginServer
output vaultName string = vault.name
output frontendName string = frontend.name
output frontendOrigin string = 'https://${frontend.properties.defaultHostname}'
output apiUrls object = {
  auth: 'https://${resourcePrefix}-auth.${environment.properties.defaultDomain}'
  projects: 'https://${resourcePrefix}-projects.${environment.properties.defaultDomain}'
  backlog: 'https://${resourcePrefix}-backlog.${environment.properties.defaultDomain}'
}
output identities object = { auth: identities[0].properties.principalId, projects: identities[1].properties.principalId, backlog: identities[2].properties.principalId }
