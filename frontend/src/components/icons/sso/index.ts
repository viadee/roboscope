import type { Component } from 'vue'
import AzureAdIcon from './AzureAdIcon.vue'
import GenericOidcIcon from './GenericOidcIcon.vue'
import GithubIcon from './GithubIcon.vue'
import GoogleIcon from './GoogleIcon.vue'

export { AzureAdIcon, GenericOidcIcon, GithubIcon, GoogleIcon }

export function iconForProviderType(providerType: string): Component {
  switch (providerType) {
    case 'oidc_azure_ad':
      return AzureAdIcon
    case 'oidc_google':
      return GoogleIcon
    case 'oidc_github':
      return GithubIcon
    default:
      return GenericOidcIcon
  }
}
