pub mod database;
pub mod handlers;
mod utils;

use std::collections::HashMap;
use std::sync::Arc;

use crate::models::User;
use crate::services::UserService;
use self::helpers::validate;
use super::common::Config;

pub struct App {
    pub db: Arc<Database>,
    pub config: Config,
}

pub enum AppMode {
    Development,
    Production,
}

pub trait Runnable {
    fn run(&self) -> Result<(), AppError>;
}

pub fn create_app(config: Config) -> App {
    let db = database::connect(&config.database_url);
    App {
        db: Arc::new(db),
        config,
    }
}

pub async fn start_server() -> Result<(), Box<dyn std::error::Error>> {
    let app = create_app(Config::load()?);
    let cache = HashMap::<String, User>::new();
    Ok(())
}