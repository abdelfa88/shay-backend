// Ce fichier est un exemple de ce que vous devriez implémenter côté serveur
// Il ne doit PAS être inclus dans votre code frontend

// Exemple d'implémentation avec Express.js
const express = require('express');
const router = express.Router();
const Stripe = require('stripe');

// Initialiser Stripe avec la clé secrète (côté serveur uniquement)
const stripe = new Stripe(process.env.STRIPE_SECRET_KEY);

router.post('/api/create-stripe-account', async (req, res) => {
  try {
    // Récupérer les données du formulaire
    const formData = req.body;
    
    // Créer le compte Stripe
    const account = await stripe.accounts.create({
      type: 'custom',
      email: formData.email,
      country: 'FR',
      capabilities: {
        card_payments: { requested: true },
        transfers: { requested: true },
      },
      business_type: formData.business_type || 'individual',
      business_profile: {
        name: `${formData.first_name} ${formData.last_name}`,
        url: formData.website || 'https://example.com',
      },
      individual: {
        first_name: formData.first_name,
        last_name: formData.last_name,
        phone: formData.phone,
        dob: {
          day: parseInt(formData.dob_day),
          month: parseInt(formData.dob_month),
          year: parseInt(formData.dob_year)
        },
        address: {
          line1: formData.address_line1,
          city: formData.address_city,
          postal_code: formData.address_postal_code,
          country: 'FR'
        }
      },
      external_account: {
        object: 'bank_account',
        country: 'FR',
        currency: 'eur',
        account_number: formData.iban.replace(/\s/g, '')
      },
      settings: {
        payouts: {
          schedule: {
            interval: 'manual'
          }
        },
        payments: {
          statement_descriptor: 'SHAY BEAUTY'
        }
      },
      tos_acceptance: {
        date: Math.floor(Date.now() / 1000),
        ip: req.ip,
        service_agreement: 'full'
      }
    });

    // Renvoyer l'ID du compte créé
    res.json({ id: account.id });
  } catch (error) {
    console.error('Error creating Stripe account:', error);
    res.status(400).json({ 
      error: {
        message: error.message || 'Erreur lors de la création du compte Stripe'
      }
    });
  }
});

module.exports = router;