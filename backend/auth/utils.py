import os
from xdk import Client

def get_client(auth_type='bearer'):
    """
    Returns an XDK Client instance based on the requested authentication type.
    """
    if auth_type == 'bearer':
        bearer_token = os.getenv("X_BEARER_TOKEN")
        if not bearer_token:
            raise ValueError("X_BEARER_TOKEN not found in environment variables")
        return Client(bearer_token=bearer_token)
    
    elif auth_type == 'oauth2':
        # TODO: Implement OAuth2 flow properly
        # For now, we can pass client_id/secret if the Client supports it directly for some flows
        # or use the OAuth2PKCEAuth class found in inspection.
        raise NotImplementedError("OAuth2 not fully implemented in benchtest yet")
    
    else:
        raise ValueError(f"Unsupported auth_type: {auth_type}")
