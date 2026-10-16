targetScope = 'resourceGroup'

@minLength(3)
@maxLength(15)
param resourcePrefix string = 'mod1-demo'
param location string = resourceGroup().location
@description('A supported Static Web Apps management region; may differ from API location.')
param frontendLocation string
@minValue(1)
@description('Monthly Azure budget in the subscription billing currency. Alerts are not a spending cap.')
param monthlyBudget int
@minLength(1)
param budgetContactEmails array
param budgetStartDate string = utcNow('yyyy-MM-01')

module shared 'modules/shared.bicep' = {
  name: '${resourcePrefix}-shared'
  params: {
    resourcePrefix: resourcePrefix
    location: location
    frontendLocation: frontendLocation
  }
}

resource budget 'Microsoft.Consumption/budgets@2023-11-01' = {
  name: '${resourcePrefix}-monthly'
  properties: {
    category: 'Cost'
    amount: monthlyBudget
    timeGrain: 'Monthly'
    timePeriod: { startDate: budgetStartDate }
    notifications: {
      Half: { enabled: true, operator: 'GreaterThanOrEqualTo', threshold: 50, contactEmails: budgetContactEmails, thresholdType: 'Actual' }
      Near: { enabled: true, operator: 'GreaterThanOrEqualTo', threshold: 80, contactEmails: budgetContactEmails, thresholdType: 'Actual' }
      Full: { enabled: true, operator: 'GreaterThanOrEqualTo', threshold: 100, contactEmails: budgetContactEmails, thresholdType: 'Actual' }
    }
  }
}

output environmentName string = shared.outputs.environmentName
output registryName string = shared.outputs.registryName
output registryServer string = shared.outputs.registryServer
output vaultName string = shared.outputs.vaultName
output frontendName string = shared.outputs.frontendName
output frontendOrigin string = shared.outputs.frontendOrigin
output apiUrls object = shared.outputs.apiUrls
output identities object = shared.outputs.identities
