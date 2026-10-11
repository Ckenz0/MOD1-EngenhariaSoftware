targetScope = 'resourceGroup'

param location string = resourceGroup().location
param appName string
param environmentId string
@description('ACR image pinned by sha256 digest')
param imageReference string
param registryServer string
param identityResourceId string
@description('Versioned Key Vault URI containing the multiline RSA PEM')
param jwtKeySecretVersionUri string
param databaseSecretUri string
@description('Key Vault secret containing the trusted Supabase CA PEM')
param databaseCaSecretUri string
param jwtIssuer string
param databaseSchema string = 'mod1_identity'
@description('JSON array of explicit browser origins, such as ["https://frontend.example.com"]')
param corsOrigins string = '[]'

resource app 'Microsoft.App/containerApps@2025-01-01' = {
  name: appName
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${identityResourceId}': {}
    }
  }
  properties: {
    managedEnvironmentId: environmentId
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        allowInsecure: false
        targetPort: 8000
        transport: 'auto'
      }
      registries: [{ server: registryServer, identity: identityResourceId }]
      secrets: [
        { name: 'auth-private-key', keyVaultUrl: jwtKeySecretVersionUri, identity: identityResourceId }
        { name: 'database-url', keyVaultUrl: databaseSecretUri, identity: identityResourceId }
        { name: 'database-ca', keyVaultUrl: databaseCaSecretUri, identity: identityResourceId }
      ]
    }
    template: {
      scale: { minReplicas: 1, maxReplicas: 1 }
      volumes: [
        {
          name: 'auth-key'
          storageType: 'Secret'
          secrets: [
            { secretRef: 'auth-private-key', path: 'auth-private-key' }
            { secretRef: 'database-ca', path: 'database-ca.pem' }
          ]
        }
      ]
      containers: [
        {
          name: 'auth'
          image: imageReference
          resources: { cpu: json('0.5'), memory: '1Gi' }
          env: [
            { name: 'DATABASE_URL', secretRef: 'database-url' }
            { name: 'DATABASE_SCHEMA', value: databaseSchema }
            { name: 'JWT_PRIVATE_KEY_PATH', value: '/mnt/secrets/auth-private-key' }
            { name: 'JWT_ISSUER', value: jwtIssuer }
            { name: 'JWT_AUDIENCE', value: 'engenharia-software-api' }
            { name: 'ACCESS_TOKEN_EXPIRE_MINUTES', value: '30' }
            { name: 'CORS_ORIGINS', value: corsOrigins }
          ]
          volumeMounts: [{ volumeName: 'auth-key', mountPath: '/mnt/secrets' }]
          probes: [
            { type: 'Startup', httpGet: { path: '/health/live', port: 8000 }, periodSeconds: 5, failureThreshold: 30 }
            { type: 'Liveness', httpGet: { path: '/health/live', port: 8000 }, periodSeconds: 10, failureThreshold: 3 }
            { type: 'Readiness', httpGet: { path: '/health/ready', port: 8000 }, periodSeconds: 10, failureThreshold: 3 }
          ]
        }
      ]
    }
  }
}

output apiUrl string = 'https://${app.properties.configuration.ingress.fqdn}'
