/*
 * Copyright 2002, 2003 University of Oslo, Norway
 *
 * This file is part of Cerebrum.
 *
 * Cerebrum is free software; you can redistribute it and/or modify it
 * under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *
 * Cerebrum is distributed in the hope that it will be useful, but
 * WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with Cerebrum; if not, write to the Free Software Foundation,
 * Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.
 * Example C++ LO client
 */

#include <gro.hh>
#include <constants.hh>
#include <iostream>
#include <omniORB4/sslContext.h>
#include <sys/stat.h>

static CORBA::ORB_ptr orb = NULL;

Cerebrum_core::Gro_var connect( int argc, char** argv )
{
    // Set up the SSL context
    sslContext::certificate_authority_file = "../../../ssl/CA.crt";
    sslContext::key_file = "../../../ssl/client.pem";
    sslContext::key_file_password = "client";

    struct stat sb;
    
    if( stat( sslContext::certificate_authority_file , &sb ) < 0 )
    {
        printf( "Error: Cannot open certificate file %s.\n", sslContext::certificate_authority_file );
        return NULL;
    }

    if( stat( sslContext::key_file , &sb ) < 0 )
    {
        printf( "Error: Cannot open key file %s.\n", sslContext::key_file );
        return NULL;
    }

    CORBA::Object_var name_service = NULL;
    CosNaming::NamingContext_var root_context = NULL;
    Cerebrum_core::Gro_var gro = NULL;

    try
    {
        // Initialize the ORB
        orb = CORBA::ORB_init( argc, argv, "omniORB4" );
        // Get the name service
        name_service = orb->resolve_initial_references( "NameService" );

        if( CORBA::is_nil( name_service ) )
        {
            printf( "Error: Could not resolve name service.\n" );
            return NULL;
        }
    
        // Narrow the root context
        root_context = CosNaming::NamingContext::_narrow( name_service );
    }
    catch( CORBA::ORB::InvalidName& ex )
    {
        printf( "Error while trying to narrow root naming context.\n" );
        return NULL;
    }
    catch( ... )
    {
        printf( "Error: Gro is not running.\n" );
        return NULL;
    }

    if( CORBA::is_nil( root_context ) )
    {
        printf( "Error while trying to narrow root naming context.\n" );
        return NULL;
    }

    // Fetch Gro using the name service
    CosNaming::Name name;
    name.length( 2 );
    name[0].id = ( const char* )CONTEXT_NAME;
    name[0].kind = ( const char* )GRO_SERVICE_NAME;
    name[1].id = ( const char* )GRO_OBJECT_NAME;
    name[1].kind = "";

    try
    {
        gro = Cerebrum_core::Gro::_narrow( root_context->resolve( name ) );
    }
    catch( CosNaming::NamingContext::NotFound& ex )
    {
        printf( "Could not narrow the Gro object.\n" );
    }
    if( CORBA::is_nil( gro ) )
    {
        printf( "Could not narrow the Gro object.\n" );
        return NULL;
    }
    return gro;
}

void disconnect()
{
    if( orb != NULL )
        orb->destroy();
}
    
void print_items( Cerebrum_core::BulkIterator_var iterator )
{
    Cerebrum_core::IterSeq_var items = NULL;
    // Iterate through all items and print their keys and values
    // (the items in the Iterator are sequences of KeyValue-objects
    while( !iterator->is_empty() )
    {
        items = iterator->next();
        for( unsigned int i = 0; i < items->length(); i++ )
        {
            printf( "-\n" );
            for( unsigned int j = 0; j < items[i].length(); j++ )
            {
                printf( "%s - %s\n", ( char* )items[i][j].key, ( char* )items[i][j].value );
            }
        }
    }
}   
                     

int main( int argc, char** argv )
{
    // Connect to Gro and fetch the server object
    Cerebrum_core::Gro_var gro = connect( argc, argv );

    // Get the version
    Cerebrum_core::Version gro_version = gro->get_version();
    printf( "Connected to Gro version %d.%d\n", gro_version.major, gro_version.minor );

    // Get the LO handler
    Cerebrum_core::LOHandler_var lo_handler = NULL;
    lo_handler = Cerebrum_core::LOHandler::_narrow( gro->get_lo_handler() );

    if( CORBA::is_nil( lo_handler ) )
    {
        printf( "Unable to retrieve LOHandler from Gro!\n" );
        return 1;
    }

    // What classes do we want to fetch?
    char* type_classes[] = { "PosixUser", "PosixGroup" };
    unsigned int len_classes = 2;

    // No spreads (string sequence of length 0)
    Cerebrum_core::StringSeq spread_seq = Cerebrum_core::StringSeq( 0 );
    Cerebrum_core::StringSeq_var spreads = Cerebrum_core::StringSeq_var( &spread_seq );

    Cerebrum_core::BulkIterator_var entities = NULL;
    Cerebrum_core::BulkIterator_var deleted = NULL;
    
    // Go through all the types in type_classes, and fetch their entities
    for( unsigned int i = 0; i < len_classes; i++ )
    {
        // Get entities. The method returns the latest change id.
        long latest = lo_handler->get_all( 
                entities, // The entities that are found
                type_classes[i], // PosixUser and PosixGroup
                spreads  // No spreads. If we want spreads, send a StringSeq&
            );

        // Print the type we've fetched
        printf( "%s\n", type_classes[i] );

        // Print what we found
        print_items( entities );

        // Print the latest change ID
        printf( "latest changeid: %i\n", latest );
    }

    // Fetch an update from change ID 1 for the previously used type classes
    for( unsigned int i = 0; i < len_classes; i++ )
    {
        // Get entities. The method returns the latest change id.
        long latest = lo_handler->get_update( 
                entities, // The entities that have changed
                deleted, // IDs of deleted entities
                type_classes[i], // PosixUser and PosixGroup
                spreads,  // No spreads. If we want spreads, send a StringSeq&
                1   // Get from id 1
            );

        // Print the type we've fetched
        printf( "%s\n", type_classes[i] );

        // Print what we found
        print_items( entities );
        print_items( deleted );

        // Print the latest change ID
        printf( "latest changeid: %i\n", latest );
    }

    // Disconnect
    disconnect();
    
    return 0;
}
