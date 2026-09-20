import { useCallback, useEffect, useState } from 'react'
import { PeraWalletConnect } from '@perawallet/connect'

const configuredChainId = Number(import.meta.env.VITE_ALGORAND_CHAIN_ID || 416001)

// Keep one client for the lifetime of the app so Pera can restore its session.
export const peraWallet = new PeraWalletConnect({
  chainId: configuredChainId,
})

export const peraChainId = configuredChainId

export function usePeraWallet() {
  const [accountAddress, setAccountAddress] = useState(null)
  const [connecting, setConnecting] = useState(false)
  const [error, setError] = useState(null)

  const disconnect = useCallback(() => {
    peraWallet.disconnect()
    setAccountAddress(null)
    setError(null)
  }, [])

  useEffect(() => {
    const handleDisconnect = () => {
      setAccountAddress(null)
    }

    peraWallet.connector?.on('disconnect', handleDisconnect)
    peraWallet.reconnectSession()
      .then((accounts) => {
        if (peraWallet.isConnected && accounts.length) {
          setAccountAddress(accounts[0])
        }
      })
      .catch(() => {
        // A missing or expired session is a normal first-visit state.
      })

    return () => {
      peraWallet.connector?.off?.('disconnect', handleDisconnect)
    }
  }, [])

  const connect = useCallback(async () => {
    setConnecting(true)
    setError(null)
    try {
      const accounts = await peraWallet.connect()
      peraWallet.connector?.on('disconnect', disconnect)
      const address = accounts[0] || null
      setAccountAddress(address)
      return address
    } catch (connectError) {
      if (connectError?.data?.type !== 'CONNECT_MODAL_CLOSED') {
        setError('Pera Wallet could not be connected.')
      }
      return null
    } finally {
      setConnecting(false)
    }
  }, [disconnect])

  const signTransactions = useCallback(async (transactionGroups) => {
    if (!accountAddress) {
      throw new Error('Connect Pera Wallet before signing a payment.')
    }
    return peraWallet.signTransaction(transactionGroups)
  }, [accountAddress])

  return {
    accountAddress,
    chainId: peraChainId,
    connecting,
    connected: Boolean(accountAddress),
    error,
    connect,
    disconnect,
    signTransactions,
  }
}
